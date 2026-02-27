"""
Module purpose:
- Verify local LLM integration scaffolding without network calls.

Checks:
1. Context snapshot contains required major sections.
2. Prompt builders can generate non-empty Chinese prompts.
3. Command block extractor can parse `[command]` sections.
4. Pipeline command logs include time and command fields.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend import CommandPipeline, GameEngine, GlobalConfig, PlayerRole, Role, build_default_campus_map
from backend.llm_agent_bridge import extract_command_blocks
from backend.llm_prompting import build_lazy_npc_prompt, build_narrative_prompt
from backend.state_snapshot import build_step_context


def assert_true(cond: bool, message: str) -> None:
    if not cond:
        raise AssertionError(message)


def main() -> None:
    campus = build_default_campus_map()
    cfg = GlobalConfig()
    engine = GameEngine(campus, cfg)
    p1 = PlayerRole("主控玩家", campus, cfg, "东教学楼内部")
    engine.register_player(p1)
    engine.set_main_player("主控玩家")
    Role("李再斌", campus, cfg, "宿舍")
    pipeline = CommandPipeline(engine)

    pipeline.compile_line("global.main_player=主控玩家")
    pipeline.compile_line("time.advance=0.5")
    logs = pipeline.get_recent_logs(15)
    assert_true(bool(logs), "logs should not be empty")
    assert_true("time" in logs[-1] and "command" in logs[-1], "log should include time and command")

    context = build_step_context(
        engine=engine,
        pipeline=pipeline,
        recent_user_turns=["用户：看下情况", "系统：你在教室里。"],
        current_user_input="我先观察周围。",
    )
    for key in (
        "world_base_setting",
        "global_state",
        "main_player_state",
        "current_scene",
        "console_syntax",
        "recent_command_logs",
    ):
        assert_true(key in context, f"context missing key: {key}")

    main_prompt = build_narrative_prompt(context)
    npc_prompt = build_lazy_npc_prompt(context, related_roles=["李再斌"])
    assert_true("【剧情】" in main_prompt or "[command]" in main_prompt, "main prompt should contain output format hints")
    assert_true("[command]" in npc_prompt, "npc prompt should mention command block")

    text = "剧情...\n[command]\ntime.advance=0.5\nglobal.battle=none\n[/command]\n选项..."
    blocks = extract_command_blocks(text)
    assert_true(len(blocks) == 1, "should extract one command block")
    assert_true("time.advance=0.5" in blocks[0], "command block text mismatch")

    print("PASS: llm prompt smoke test")


if __name__ == "__main__":
    main()
