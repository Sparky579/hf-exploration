"""
Module purpose:
- Coordinate one game step with:
  1) main narrative stream request (player-facing),
  2) hidden enemy-trigger request (enemy-only, window pre-processing).

Functions:
- extract_command_blocks(text): pull command blocks wrapped in [command]...[/command].

Class:
- LLMAgentBridge
  - run_step_stream(...): stream narrative chunks and apply parsed commands.
  - Enemy logic:
    - bootstrap initial enemy trigger once,
    - each round pre-promote enemy triggers within [N, N+1],
    - hidden thread handles these due triggers in parallel with narrative stream,
    - ensure each alive enemy has a next future trigger.
"""

from __future__ import annotations

import re
from collections.abc import Generator
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from .command_pipeline import CommandPipeline
from .gemini_client import GeminiClient
from .llm_prompting import (
    build_enemy_initial_trigger_prompt,
    build_enemy_trigger_prompt,
    build_narrative_prompt,
)
from .state_snapshot import build_step_context


def extract_command_blocks(text: str) -> list[str]:
    """Extract command block payloads from `[command]...[/command]` sections."""

    if not text:
        return []
    pattern = re.compile(r"\[command\](.*?)\[/command\]", re.IGNORECASE | re.DOTALL)
    return [m.strip() for m in pattern.findall(text) if m.strip()]


class LLMAgentBridge:
    """Bridge runtime game state with stream narrative + enemy trigger processor."""

    def __init__(self, client: GeminiClient) -> None:
        self.client = client
        self._enemy_bootstrapped = False

    def run_step_stream(
        self,
        pipeline: CommandPipeline,
        recent_user_turns: list[str],
        current_user_input: str,
        apply_commands: bool = True,
    ) -> Generator[dict[str, Any], None, None]:
        """
        Stream one step:
        - yield narrative chunks as they arrive,
        - then return final packet with parsed/applied commands and hidden-thread outputs.
        """

        applied: list[str] = []
        errors: list[str] = []
        init_enemy_text = ""
        enemy_text = ""

        context = build_step_context(
            engine=pipeline.engine,
            pipeline=pipeline,
            recent_user_turns=recent_user_turns,
            current_user_input=current_user_input,
        )
        enemy_roles = self._alive_enemy_roles(context)

        # Bootstrap first triggers for enemies once.
        if apply_commands and enemy_roles:
            init_enemy_text = self._bootstrap_enemy_triggers_if_needed(
                pipeline, context, enemy_roles, applied, errors
            )
            context = build_step_context(
                engine=pipeline.engine,
                pipeline=pipeline,
                recent_user_turns=recent_user_turns,
                current_user_input=current_user_input,
            )

        now = float(context["global_state"]["time"])
        enemy_window_end = now + 1.0
        promoted_ids: list[int] = []
        if apply_commands and enemy_roles:
            promoted_ids = self._promote_enemy_triggers_in_window(
                pipeline, enemy_roles, window_end=enemy_window_end
            )
            if promoted_ids:
                context = build_step_context(
                    engine=pipeline.engine,
                    pipeline=pipeline,
                    recent_user_turns=recent_user_turns,
                    current_user_input=current_user_input,
                )

        due_enemy_triggers = self._collect_due_enemy_triggers(context, enemy_roles, enemy_window_end)
        narrative_prompt = build_narrative_prompt(context)
        enemy_prompt = (
            build_enemy_trigger_prompt(context, enemy_roles, due_enemy_triggers)
            if due_enemy_triggers
            else ""
        )

        with ThreadPoolExecutor(max_workers=1) as executor:
            enemy_future: Future[str] | None = None
            if enemy_prompt:
                enemy_future = executor.submit(self.client.generate_text, enemy_prompt)

            main_chunks: list[str] = []
            for chunk in self.client.stream_generate_text(narrative_prompt):
                main_chunks.append(chunk)
                yield {"type": "narrative_chunk", "text": chunk}
            main_text = "".join(main_chunks)

            if enemy_future is not None:
                enemy_text = enemy_future.result()

        enemy_commands = self._flatten_commands(enemy_text)
        narrative_commands = self._flatten_commands(main_text)

        if apply_commands:
            self._apply_commands(
                pipeline=pipeline,
                commands=enemy_commands,
                applied=applied,
                errors=errors,
                source="Enemy",
                allow_time_advance=False,
            )
            for item in due_enemy_triggers:
                try:
                    pipeline.engine.global_config.mark_trigger_handled(int(item["id"]))
                except Exception as exc:
                    errors.append(f"Enemy trigger handled-mark failed: #{item['id']} -> {exc}")

            self._apply_commands(
                pipeline=pipeline,
                commands=narrative_commands,
                applied=applied,
                errors=errors,
                source="Narrative",
                allow_time_advance=True,
            )
            self._ensure_future_enemy_triggers(pipeline, enemy_roles, applied)

        yield {
            "type": "final",
            "main_text": main_text,
            "enemy_init_text": init_enemy_text,
            "enemy_text": enemy_text,
            "enemy_roles": enemy_roles,
            "enemy_window_end": enemy_window_end,
            "promoted_enemy_trigger_ids": promoted_ids,
            "due_enemy_triggers": due_enemy_triggers,
            "narrative_commands": narrative_commands,
            "enemy_commands": enemy_commands,
            "applied_commands": applied,
            "errors": errors,
        }

    def _bootstrap_enemy_triggers_if_needed(
        self,
        pipeline: CommandPipeline,
        context: dict[str, Any],
        enemy_roles: list[str],
        applied: list[str],
        errors: list[str],
    ) -> str:
        if self._enemy_bootstrapped:
            return ""

        missing_roles = [
            role for role in enemy_roles if not pipeline.engine.global_config.has_any_trigger_for_owner(role)
        ]
        if not missing_roles:
            self._enemy_bootstrapped = True
            return ""

        prompt = build_enemy_initial_trigger_prompt(context, missing_roles)
        text = self.client.generate_text(prompt)
        commands = self._flatten_commands(text)
        self._apply_commands(
            pipeline=pipeline,
            commands=commands,
            applied=applied,
            errors=errors,
            source="EnemyInit",
            allow_time_advance=False,
        )

        now = float(pipeline.engine.global_config.current_time_unit)
        # Fallback: ensure at least one trigger exists for each missing enemy.
        for role in missing_roles:
            if pipeline.engine.global_config.has_any_trigger_for_owner(role):
                continue
            fallback = (
                f"trigger.add=owner:{role}|time {now + 1:g} "
                f"if {role} alive and not left then {role} idle"
            )
            try:
                pipeline.compile_line(fallback)
                applied.append(fallback)
            except Exception as exc:
                errors.append(f"EnemyInit fallback failed: {role} -> {exc}")
        self._enemy_bootstrapped = True
        return text

    def _promote_enemy_triggers_in_window(
        self,
        pipeline: CommandPipeline,
        enemy_roles: list[str],
        window_end: float,
    ) -> list[int]:
        promoted: list[int] = []
        now = float(pipeline.engine.global_config.current_time_unit)
        for item in pipeline.engine.global_config.scripted_triggers:
            owner = str(item.get("owner", ""))
            if owner not in enemy_roles:
                continue
            if bool(item.get("handled", False)) or bool(item.get("triggered", False)):
                continue
            trigger_time = float(item.get("trigger_time", 0.0))
            if trigger_time > window_end:
                continue
            # Window pre-processing: force fire now so hidden thread can handle in this round.
            pipeline.engine.global_config.mark_trigger_fired(int(item["id"]))
            pipeline.engine.event_checker.state.trigger_history.append(
                f"t={now}: window-fire enemy trigger#{item['id']} (time={trigger_time})"
            )
            promoted.append(int(item["id"]))
        return promoted

    def _collect_due_enemy_triggers(
        self,
        context: dict[str, Any],
        enemy_roles: list[str],
        window_end: float,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        triggers = context["global_state"].get("scripted_triggers", [])
        for item in triggers:
            if str(item.get("owner", "")) not in enemy_roles:
                continue
            if not bool(item.get("triggered", False)):
                continue
            if bool(item.get("handled", False)):
                continue
            if float(item.get("trigger_time", 0.0)) > float(window_end):
                continue
            rows.append(item)
        rows.sort(key=lambda x: (float(x.get("trigger_time", 0.0)), int(x.get("id", 0))))
        return rows

    def _ensure_future_enemy_triggers(
        self,
        pipeline: CommandPipeline,
        enemy_roles: list[str],
        applied: list[str],
    ) -> None:
        now = float(pipeline.engine.global_config.current_time_unit)
        for role in enemy_roles:
            if not self._role_is_alive(pipeline, role):
                continue
            if pipeline.engine.global_config.has_future_trigger_for_owner(role, now=now):
                continue
            line = (
                f"trigger.add=owner:{role}|time {now + 1:g} "
                f"if {role} alive and not left then {role} idle"
            )
            pipeline.compile_line(line)
            applied.append(line)

    @staticmethod
    def _role_is_alive(pipeline: CommandPipeline, role_name: str) -> bool:
        if role_name in pipeline.engine.character_profiles:
            profile = pipeline.engine.get_character_profile(role_name)
            if profile.status != "存活":
                return False
        if role_name in pipeline.engine.campus_map.roles:
            role = pipeline.engine.get_role(role_name)
            return role.health > 0
        return False

    @staticmethod
    def _alive_enemy_roles(context: dict[str, Any]) -> list[str]:
        rows: list[str] = []
        for name, profile in context["character_profiles"].items():
            alignment = str(profile.get("alignment", ""))
            status = str(profile.get("status", ""))
            if "敌对" not in alignment:
                continue
            if status != "存活":
                continue
            rows.append(name)
        return rows

    @staticmethod
    def _apply_commands(
        pipeline: CommandPipeline,
        commands: list[str],
        applied: list[str],
        errors: list[str],
        source: str,
        allow_time_advance: bool,
    ) -> None:
        for line in commands:
            if (not allow_time_advance) and line.startswith("time.advance"):
                continue
            try:
                pipeline.compile_line(line)
                applied.append(line)
            except Exception as exc:
                errors.append(f"{source} command failed: {line} -> {exc}")

    @staticmethod
    def _flatten_commands(text: str) -> list[str]:
        blocks = extract_command_blocks(text)
        lines: list[str] = []
        for block in blocks:
            for raw in block.splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                # Unified command line format: [<command>]
                if line.startswith("[") and line.endswith("]"):
                    inner = line[1:-1].strip()
                    if inner:
                        line = inner
                lines.append(line)
        return lines
