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
    - after narrative time jumps, run one immediate catch-up pass for newly-fired enemy triggers,
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
        backend_step_notes: list[str] | None = None,
        allow_narrative_time_advance: bool = True,
        block_main_player_move: bool = False,
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
        enemy_post_text = ""

        context = build_step_context(
            engine=pipeline.engine,
            pipeline=pipeline,
            recent_user_turns=recent_user_turns,
            current_user_input=current_user_input,
            backend_step_notes=backend_step_notes,
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
                backend_step_notes=backend_step_notes,
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
                    backend_step_notes=backend_step_notes,
                )

        due_enemy_triggers = self._collect_due_enemy_triggers(context, enemy_roles, enemy_window_end)
        if apply_commands and enemy_roles:
            due_enemy_triggers = self._ensure_battle_enemy_due_trigger(
                pipeline=pipeline,
                context=context,
                enemy_roles=enemy_roles,
                due_enemy_triggers=due_enemy_triggers,
                applied=applied,
                errors=errors,
            )
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
            self._flush_enemy_queue_if_needed(pipeline, enemy_commands, applied, errors)
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
                allow_time_advance=allow_narrative_time_advance,
                block_main_player_move=block_main_player_move,
            )
            self._flush_queue_if_needed(
                pipeline=pipeline,
                commands=narrative_commands,
                applied=applied,
                errors=errors,
                source="Narrative",
            )
            enemy_post_text = self._run_enemy_catchup_after_narrative(
                pipeline=pipeline,
                recent_user_turns=recent_user_turns,
                current_user_input=current_user_input,
                backend_step_notes=backend_step_notes,
                enemy_roles=enemy_roles,
                applied=applied,
                errors=errors,
            )
            self._ensure_future_enemy_triggers(pipeline, enemy_roles, applied)

        yield {
            "type": "final",
            "main_text": main_text,
            "enemy_init_text": init_enemy_text,
            "enemy_text": enemy_text,
            "enemy_post_text": enemy_post_text,
            "enemy_roles": enemy_roles,
            "enemy_window_end": enemy_window_end,
            "promoted_enemy_trigger_ids": promoted_ids,
            "due_enemy_triggers": due_enemy_triggers,
            "narrative_commands": narrative_commands,
            "enemy_commands": enemy_commands,
            "applied_commands": applied,
            "errors": errors,
        }

    def _run_enemy_catchup_after_narrative(
        self,
        pipeline: CommandPipeline,
        recent_user_turns: list[str],
        current_user_input: str,
        backend_step_notes: list[str] | None,
        enemy_roles: list[str],
        applied: list[str],
        errors: list[str],
    ) -> str:
        """
        After narrative commands are applied, process any enemy triggers that became due
        because of this round's time jump (e.g. [time.advance=2]).
        """

        if not enemy_roles:
            return ""
        context = build_step_context(
            engine=pipeline.engine,
            pipeline=pipeline,
            recent_user_turns=recent_user_turns,
            current_user_input=current_user_input,
            backend_step_notes=backend_step_notes,
        )
        now = float(context["global_state"]["time"])
        due_enemy_triggers = self._collect_due_enemy_triggers(context, enemy_roles, window_end=now)
        due_enemy_triggers = self._ensure_battle_enemy_due_trigger(
            pipeline=pipeline,
            context=context,
            enemy_roles=enemy_roles,
            due_enemy_triggers=due_enemy_triggers,
            applied=applied,
            errors=errors,
        )
        if not due_enemy_triggers:
            return ""

        prompt = build_enemy_trigger_prompt(context, enemy_roles, due_enemy_triggers)
        text = self.client.generate_text(prompt)
        commands = self._flatten_commands(text)
        self._apply_commands(
            pipeline=pipeline,
            commands=commands,
            applied=applied,
            errors=errors,
            source="EnemyCatchup",
            allow_time_advance=False,
        )
        self._flush_enemy_queue_if_needed(pipeline, commands, applied, errors)
        for item in due_enemy_triggers:
            try:
                pipeline.engine.global_config.mark_trigger_handled(int(item["id"]))
            except Exception as exc:
                errors.append(f"EnemyCatchup handled-mark failed: #{item['id']} -> {exc}")
        return text

    def _ensure_battle_enemy_due_trigger(
        self,
        pipeline: CommandPipeline,
        context: dict[str, Any],
        enemy_roles: list[str],
        due_enemy_triggers: list[dict[str, Any]],
        applied: list[str],
        errors: list[str],
    ) -> list[dict[str, Any]]:
        """
        Ensure hidden enemy thread has one due trigger in battle rounds so enemy can react/deploy.
        """

        battle_target = str(context.get("global_state", {}).get("battle_state") or "")
        if not battle_target or battle_target not in enemy_roles:
            return due_enemy_triggers
        if not self._role_is_alive(pipeline, battle_target):
            return due_enemy_triggers
        if any(str(item.get("owner", "")) == battle_target for item in due_enemy_triggers):
            return due_enemy_triggers

        now = float(context.get("global_state", {}).get("time", 0.0))
        trigger_sentence = (
            f"owner:{battle_target}|time {now:g} if {battle_target} alive and in battle "
            f"then {battle_target} battle_react"
        )
        line = f"trigger.add={trigger_sentence}"
        try:
            item = pipeline.engine.global_config.add_scripted_trigger(trigger_sentence)
            pipeline.engine.global_config.mark_trigger_fired(int(item["id"]))
            applied.append(line)
        except Exception as exc:
            errors.append(f"Battle enemy trigger inject failed: {battle_target} -> {exc}")
            return due_enemy_triggers

        refreshed = build_step_context(
            engine=pipeline.engine,
            pipeline=pipeline,
            recent_user_turns=context.get("recent_user_turns", []),
            current_user_input=str(context.get("current_user_input", "")),
            backend_step_notes=context.get("backend_step_notes"),
        )
        refreshed_due = self._collect_due_enemy_triggers(
            refreshed, enemy_roles, window_end=float(refreshed["global_state"]["time"])
        )
        return refreshed_due

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
        if missing_roles:
            self._seed_default_enemy_initial_triggers(pipeline, missing_roles, applied, errors)
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

        # Fallback: ensure at least one trigger exists for each missing enemy.
        for role in missing_roles:
            if pipeline.engine.global_config.has_any_trigger_for_owner(role):
                continue
            fallback = self._build_idle_trigger_line(pipeline, role)
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
            line = self._build_idle_trigger_line(pipeline, role)
            pipeline.compile_line(line)
            applied.append(line)

    def _seed_default_enemy_initial_triggers(
        self,
        pipeline: CommandPipeline,
        roles: list[str],
        applied: list[str],
        errors: list[str],
    ) -> None:
        defaults = {
            "李再斌": "trigger.add=owner:李再斌|time 7 if 李再斌 alive and not left then 李再斌 deploy 皮卡超人",
            "颜宏帆": "trigger.add=owner:颜宏帆|time 9 if 颜宏帆 alive and not left then 颜宏帆 deploy 野猪骑士",
        }
        for role in roles:
            line = defaults.get(role, self._build_idle_trigger_line(pipeline, role))
            try:
                pipeline.compile_line(line)
                applied.append(line)
            except Exception as exc:
                errors.append(f"EnemyInit default failed: {role} -> {exc}")

    def _build_idle_trigger_line(self, pipeline: CommandPipeline, role: str) -> str:
        next_time = self._next_trigger_time_for_owner(pipeline, role)
        return f"trigger.add=owner:{role}|time {next_time:g} if {role} alive and not left then {role} idle"

    @staticmethod
    def _next_trigger_time_for_owner(pipeline: CommandPipeline, role: str) -> float:
        now = float(pipeline.engine.global_config.current_time_unit)
        latest = pipeline.engine.global_config.get_latest_trigger_time_for_owner(role)
        if latest is None:
            return now + 1.0
        return max(now + 1.0, float(latest) + 1.0)

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
        block_main_player_move: bool = False,
    ) -> None:
        main_player = pipeline.engine.main_player_name or ""
        for line in commands:
            if (not allow_time_advance) and line.startswith("time.advance"):
                continue
            if block_main_player_move and main_player and line.startswith(f"{main_player}.move"):
                errors.append(f"{source} command blocked: {line} -> main player move is backend-handled this round")
                continue
            if LLMAgentBridge._is_forbidden_holy_water_command(source, line):
                errors.append(f"{source} command blocked: {line} -> holy_water is system-managed")
                continue
            try:
                pipeline.compile_line(line)
                applied.append(line)
            except Exception as exc:
                errors.append(f"{source} command failed: {line} -> {exc}")

    @staticmethod
    def _flush_enemy_queue_if_needed(
        pipeline: CommandPipeline,
        enemy_commands: list[str],
        applied: list[str],
        errors: list[str],
    ) -> None:
        """Ensure enemy move/deploy queue actions are executed in this round."""

        if not enemy_commands:
            return
        has_queue_action = any(".move=" in line or ".deploy=" in line for line in enemy_commands)
        has_explicit_flush = any(line.strip() == "queue.flush=true" for line in enemy_commands)
        if (not has_queue_action) or has_explicit_flush:
            return
        try:
            pipeline.compile_line("queue.flush=true")
            applied.append("queue.flush=true")
        except Exception as exc:
            errors.append(f"Enemy auto queue.flush failed: {exc}")

    @staticmethod
    def _flush_queue_if_needed(
        pipeline: CommandPipeline,
        commands: list[str],
        applied: list[str],
        errors: list[str],
        source: str,
    ) -> None:
        """
        Ensure queued move/deploy commands from model are executed even if queue.flush is omitted.
        """

        if not commands:
            return
        has_queue_action = any(".move=" in line or ".deploy=" in line for line in commands)
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
        For model-generated commands, holy water is runtime-managed by time/deploy rules.
        """

        # if source not in ("Narrative", "Enemy", "EnemyInit"):
        #     return False
        # normalized = line.strip().lower()
        # return ".holy_water" in normalized
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
                # Unified command line format: [<command>]
                if line.startswith("[") and line.endswith("]"):
                    inner = line[1:-1].strip()
                    if inner:
                        line = inner
                lines.append(line)
        return lines
