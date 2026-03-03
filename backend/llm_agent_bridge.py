"""
Bridge runtime game state with main narrative LLM stream.

Enemy-side control is intentionally deterministic and handled by `EnemyDirector`
in engine time flow. This bridge now only performs:
- main narrative prompt build,
- streaming narrative text / thinking ticks,
- command extraction and execution.
"""

from __future__ import annotations

import re
from collections.abc import Generator
from typing import Any

from .command_pipeline import CommandPipeline
from .llm_prompting import _build_prompt_compact_context, build_narrative_prompt
from .state_snapshot import build_step_context


def extract_command_blocks(text: str) -> list[str]:
    """Extract command block payloads from `[command]...[/command]` sections."""

    if not text:
        return []
    pattern = re.compile(r"\[command\](.*?)\[/command\]", re.IGNORECASE | re.DOTALL)
    return [m.strip() for m in pattern.findall(text) if m.strip()]


class LLMAgentBridge:
    """Main narrative stream runner and command applier."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def run_step_stream(
        self,
        pipeline: CommandPipeline,
        recent_user_turns: list[str],
        current_user_input: str,
        apply_commands: bool = True,
        backend_step_notes: list[str] | None = None,
        allow_narrative_time_advance: bool = True,
        block_main_player_move: bool = False,
        freeze_time_position_updates: bool = False,
    ) -> Generator[dict[str, Any], None, None]:
        """
        Stream one step:
        - yield narrative chunks and thinking ticks during generation,
        - return one final packet with parsed/applied command details.
        """

        applied: list[str] = []
        errors: list[str] = []

        context = build_step_context(
            engine=pipeline.engine,
            pipeline=pipeline,
            recent_user_turns=recent_user_turns,
            current_user_input=current_user_input,
            backend_step_notes=backend_step_notes,
        )
        now = float(context["global_state"]["time"])
        compact_context = _build_prompt_compact_context(context)
        narrative_prompt = build_narrative_prompt(context)
        yield {"type": "prompt", "narrative_prompt": narrative_prompt}

        main_chunks: list[str] = []
        thinking_active = False
        thinking_tick = 0
        for part in self.client.stream_generate_parts(narrative_prompt):
            text = str(part.get("text", ""))
            if not text:
                continue
            if bool(part.get("thought", False)):
                if not thinking_active:
                    thinking_active = True
                    yield {"type": "thinking", "status": "start", "tick": thinking_tick}
                thinking_tick += 1
                yield {"type": "thinking", "status": "tick", "tick": thinking_tick}
                continue
            if thinking_active:
                thinking_active = False
                yield {"type": "thinking", "status": "done", "tick": thinking_tick}
            main_chunks.append(text)
            yield {"type": "narrative_chunk", "text": text}
        if thinking_active:
            yield {"type": "thinking", "status": "done", "tick": thinking_tick}
        main_text = "".join(main_chunks)

        narrative_commands = self._flatten_commands(main_text)
        if apply_commands:
            self._apply_commands(
                pipeline=pipeline,
                commands=narrative_commands,
                applied=applied,
                errors=errors,
                source="Narrative",
                allow_time_advance=allow_narrative_time_advance,
                block_main_player_move=block_main_player_move,
                freeze_time_position_updates=freeze_time_position_updates,
            )
            self._flush_queue_if_needed(
                pipeline=pipeline,
                commands=narrative_commands,
                applied=applied,
                errors=errors,
                source="Narrative",
            )

        yield {
            "type": "final",
            "interrupted": False,
            "step_context": compact_context,
            "narrative_prompt": narrative_prompt,
            "enemy_prompt": "",
            "main_text": main_text,
            "enemy_init_text": "",
            "enemy_text": "",
            "enemy_post_text": "",
            "enemy_roles": [],
            "enemy_window_end": now + 1.0,
            "promoted_enemy_trigger_ids": [],
            "due_enemy_triggers": [],
            "narrative_commands": narrative_commands,
            "enemy_commands": [],
            "applied_commands": applied,
            "errors": errors,
        }

    @staticmethod
    def _apply_commands(
        pipeline: CommandPipeline,
        commands: list[str],
        applied: list[str],
        errors: list[str],
        source: str,
        allow_time_advance: bool,
        block_main_player_move: bool = False,
        freeze_time_position_updates: bool = False,
    ) -> None:
        main_player = pipeline.engine.main_player_name or ""
        has_time_advance = any(line.startswith("time.advance") for line in commands)
        event_trigger_applied = False
        for line in commands:
            left_key = LLMAgentBridge._extract_left_key(line)
            assign_op = LLMAgentBridge._extract_assign_op(line)
            if ".move=" in line:
                errors.append(f"{source} command blocked: {line} -> movement is backend-resolved")
                continue
            if freeze_time_position_updates:
                if line.startswith("time.advance"):
                    errors.append(f"{source} command blocked: {line} -> retry mode freezes time update")
                    continue
                if ".location=" in line or ".escape=" in line:
                    errors.append(f"{source} command blocked: {line} -> retry mode freezes position update")
                    continue
                if line.startswith("game_event.trigger=") or line.startswith("scene_event.trigger="):
                    errors.append(f"{source} command blocked: {line} -> retry mode blocks event-triggered time update")
                    continue
            if (not allow_time_advance) and line.startswith("time.advance"):
                continue
            if event_trigger_applied and line.startswith("time.advance"):
                errors.append(
                    f"{source} command blocked: {line} -> predefined event handles time advance automatically"
                )
                continue
            if assign_op == "=" and left_key.endswith(".nearby_units"):
                errors.append(
                    f"{source} command blocked: {line} -> nearby_units must use += / -= incremental edits"
                )
                continue
            if left_key in {"trigger.remove", "trigger.clear"}:
                errors.append(
                    f"{source} command blocked: {line} -> trigger timeline is backend-managed"
                )
                continue
            if line.startswith("game_event.trigger=") or line.startswith("scene_event.trigger="):
                event_id = line.split("=", 1)[1].strip()
                if event_id.isdigit():
                    errors.append(f"{source} command blocked: {line} -> trigger id must be event name, not number")
                    continue
            if left_key == "global.emergency":
                right = line.split("=", 1)[1].strip().lower()
                if right in {"none", "null", "nil"}:
                    line = "global.emergency=false"
            if block_main_player_move and main_player and line.startswith(f"{main_player}.move"):
                errors.append(f"{source} command blocked: {line} -> main player move is backend-handled this round")
                continue
            if main_player and line.startswith(f"{main_player}.card_valid"):
                errors.append(
                    f"{source} command blocked: {line} -> main card_valid is event-managed (install/token)"
                )
                continue
            if LLMAgentBridge._is_forbidden_holy_water_command(source, line):
                errors.append(f"{source} command blocked: {line} -> holy_water is system-managed")
                continue
            try:
                pipeline.compile_line(line)
                applied.append(line)
                if line.startswith("game_event.trigger=") or line.startswith("scene_event.trigger="):
                    event_trigger_applied = True
            except Exception as exc:
                errors.append(f"{source} command failed: {line} -> {exc}")

        # Backend safeguard: if model forgot time flow and no event trigger happened,
        # advance 0.5 to avoid frozen turns.
        if allow_time_advance and (not has_time_advance) and (not event_trigger_applied):
            try:
                pipeline.compile_line("time.advance=0.5")
                applied.append("time.advance=0.5")
            except Exception as exc:
                errors.append(f"{source} auto time.advance failed: {exc}")

    @staticmethod
    def _extract_left_key(line: str) -> str:
        """
        Extract normalized left-hand key for assignment-like commands.
        Handles spacing variants such as `global.emergency = none`.
        """
        raw = str(line or "").strip()
        if not raw:
            return ""
        for op in ("+=", "-=", "="):
            if op in raw:
                return raw.split(op, 1)[0].strip()
        return raw

    @staticmethod
    def _extract_assign_op(line: str) -> str | None:
        raw = str(line or "").strip()
        if not raw:
            return None
        for op in ("+=", "-=", "="):
            if op in raw:
                return op
        return None

    @staticmethod
    def _flush_queue_if_needed(
        pipeline: CommandPipeline,
        commands: list[str],
        applied: list[str],
        errors: list[str],
        source: str,
    ) -> None:
        """
        Ensure queued move/deploy commands are executed even if queue.flush is omitted.
        """

        if not commands:
            return
        has_queue_action = any(".deploy=" in line for line in commands)
        has_explicit_flush = any(line.strip() == "queue.flush=true" for line in commands)
        if (not has_queue_action) or has_explicit_flush:
            return
        try:
            pipeline.compile_line("queue.flush=true")
            applied.append("queue.flush=true")
        except Exception as exc:
            errors.append(f"{source} auto queue.flush failed: {exc}")

    @staticmethod
    def _is_forbidden_holy_water_command(source: str, line: str) -> bool:
        """
        Keep compatible signature; command filtering can be tightened later if needed.
        """

        _ = source
        _ = line
        return False

    @staticmethod
    def _flatten_commands(text: str) -> list[str]:
        blocks = extract_command_blocks(text)
        lines: list[str] = []
        for block in blocks:
            for raw in block.splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    inner = line[1:-1].strip()
                    if inner:
                        line = inner
                lines.append(line)
        return lines
