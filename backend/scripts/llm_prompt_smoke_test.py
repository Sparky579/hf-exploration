"""
Module purpose:
- Verify local LLM integration scaffolding without network calls.

Checks:
1. Context snapshot contains required major sections.
2. Prompt builders can generate non-empty prompts.
3. Command block extractor can parse `[command]` sections.
4. Pipeline command logs include time and command fields.
5. Trigger owner + fired/handled fields + N~N+1.5 window fields exist.
6. Bracket command format `[ ... ]` is accepted by CommandPipeline.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend import CommandPipeline, GameEngine, GlobalConfig, PlayerRole, build_default_campus_map
from backend.llm_agent_bridge import LLMAgentBridge, extract_command_blocks
from backend.llm_prompting import (
    build_enemy_initial_trigger_prompt,
    build_enemy_trigger_prompt,
    build_narrative_prompt,
)
from backend.state_snapshot import build_step_context


def assert_true(cond: bool, message: str) -> None:
    if not cond:
        raise AssertionError(message)


def main() -> None:
    campus = build_default_campus_map()
    cfg = GlobalConfig()
    engine = GameEngine(campus, cfg)
    start_node = list(campus.nodes.keys())[0]
    p1 = PlayerRole("MAIN", campus, cfg, start_node)
    engine.register_player(p1)
    engine.set_main_player("MAIN")
    pipeline = CommandPipeline(engine)

    # Bracket command syntax should work.
    pipeline.compile_line("[global.main_player=MAIN]")
    pipeline.compile_line("[trigger.add=owner:ENEMY_A|time 1 if ENEMY_A alive then ENEMY_A idle]")
    pipeline.compile_line("[time.advance=1.5]")
    logs = pipeline.get_recent_logs(15)
    assert_true(bool(logs), "logs should not be empty")
    assert_true("time" in logs[-1] and "command" in logs[-1], "log should include time and command")

    context = build_step_context(
        engine=engine,
        pipeline=pipeline,
        recent_user_turns=["User: 先观察", "System: 你在教学楼里。"],
        current_user_input="我先观察周围。",
    )
    for key in (
        "world_base_setting",
        "global_state",
        "main_player_state",
        "team_move_profile",
        "current_scene",
        "console_syntax",
        "recent_command_logs",
        "main_player_sensing_scope",
        "nearby_trigger_hints",
    ):
        assert_true(key in context, f"context missing key: {key}")

    triggers = context["global_state"]["scripted_triggers"]
    assert_true(bool(triggers), "scripted triggers should exist")
    assert_true("owner" in triggers[0], "trigger should include owner")
    assert_true("handled" in triggers[0], "trigger should include handled flag")
    assert_true("trigger_window_n_to_n_plus_1_5" in context["global_state"], "missing trigger window field")
    assert_true("main_player_move_time_cost" in context["global_state"], "missing move-time hint in global_state")
    assert_true(
        "effective_move_time_cost" in context["team_move_profile"],
        "missing move-time hint in team_move_profile",
    )

    main_prompt = build_narrative_prompt(context)
    init_prompt = build_enemy_initial_trigger_prompt(context, enemy_roles=["ENEMY_A"])
    fired = [x for x in triggers if x.get("triggered") and not x.get("handled")]
    process_prompt = build_enemy_trigger_prompt(context, enemy_roles=["ENEMY_A"], fired_enemy_triggers=fired)
    assert_true("[command]" in main_prompt, "main prompt should contain command protocol")
    assert_true("trigger.add" in init_prompt, "init prompt should mention trigger.add")
    assert_true("event.rocket_launch" in process_prompt, "process prompt should mention rocket command")

    text = "剧情...\n[command]\n[time.advance=0.5]\n[global.battle=none]\n[/command]\n选项..."
    blocks = extract_command_blocks(text)
    assert_true(len(blocks) == 1, "should extract one command block")
    assert_true("[time.advance=0.5]" in blocks[0], "command block text mismatch")

    # Enemy trigger lifecycle stability check: no duplicate pile-up when time does not move.
    class _MockClient:
        def generate_text(self, prompt: str) -> str:
            return "[command]\n[/command]"

        def stream_generate_text(self, prompt: str):
            yield "[command]\n[/command]"

    bridge = LLMAgentBridge(_MockClient())  # type: ignore[arg-type]
    for _ in bridge.run_step_stream(
        pipeline=pipeline,
        recent_user_turns=["User: x", "System: y"],
        current_user_input="wait",
        apply_commands=True,
    ):
        pass
    after_first = [
        t for t in engine.global_config.scripted_triggers if str(t["owner"]) in ("李再斌", "颜宏帆")
    ]
    for _ in bridge.run_step_stream(
        pipeline=pipeline,
        recent_user_turns=["User: x", "System: y"],
        current_user_input="wait",
        apply_commands=True,
    ):
        pass
    after_second = [
        t for t in engine.global_config.scripted_triggers if str(t["owner"]) in ("李再斌", "颜宏帆")
    ]
    assert_true(len(after_first) == len(after_second), "enemy triggers should not duplicate when time is unchanged")

    print("PASS: llm prompt smoke test")


if __name__ == "__main__":
    main()
