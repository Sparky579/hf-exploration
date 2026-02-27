"""
Module purpose:
- Verify model-command guardrails in LLMAgentBridge.

Checks:
1. Model-generated `.holy_water` commands are blocked.
2. Normal runtime updates (e.g. `time.advance`) still execute.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend import CommandPipeline, GameEngine, GlobalConfig, PlayerRole, build_default_campus_map
from backend.llm_agent_bridge import LLMAgentBridge


def assert_true(cond: bool, message: str) -> None:
    if not cond:
        raise AssertionError(message)


def assert_close(actual: float, expected: float, message: str, eps: float = 1e-9) -> None:
    if abs(float(actual) - float(expected)) > eps:
        raise AssertionError(f"{message}: expected={expected!r}, actual={actual!r}")


def main() -> None:
    campus = build_default_campus_map()
    cfg = GlobalConfig()
    engine = GameEngine(campus, cfg)
    main_player = PlayerRole("MAIN", campus, cfg, "东教学楼内部")
    engine.register_player(main_player)
    engine.set_main_player("MAIN")
    pipe = CommandPipeline(engine)

    applied: list[str] = []
    errors: list[str] = []
    LLMAgentBridge._apply_commands(
        pipeline=pipe,
        commands=["MAIN.holy_water=9", "time.advance=1"],
        applied=applied,
        errors=errors,
        source="Narrative",
        allow_time_advance=True,
    )

    assert_true(any("holy_water is system-managed" in x for x in errors), "holy_water command should be blocked")
    assert_close(main_player.holy_water, 0.5, "holy_water should only change via regen from time.advance")

    print("PASS: llm command guard test")


if __name__ == "__main__":
    main()
