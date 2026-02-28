"""
Module purpose:
- Verify narrative commands with deploy/move are auto-flushed when queue.flush is omitted.

Checks:
1. Narrative deploy without queue.flush still executes and deducts holy water.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend import CommandPipeline, GameEngine, GlobalConfig, PlayerRole, build_default_campus_map
from backend.llm_agent_bridge import LLMAgentBridge


class FakeClient:
    def stream_generate_text(self, prompt: str):
        yield (
            "[command]\n"
            "[global.main_player=主控玩家]\n"
            "[global.battle=none]\n"
            "[global.emergency=false]\n"
            "[主控玩家.holy_water=10]\n"
            "[主控玩家.deploy=地狱飞龙]\n"
            "[/command]\n"
            "剧情"
        )

    def generate_text(self, prompt: str) -> str:
        return "[command]\n[/command]"


def assert_true(cond: bool, message: str) -> None:
    if not cond:
        raise AssertionError(message)


def main() -> None:
    campus = build_default_campus_map()
    cfg = GlobalConfig()
    engine = GameEngine(campus, cfg)
    main = PlayerRole("主控玩家", campus, cfg, "东教学楼内部")
    engine.register_player(main)
    engine.set_main_player("主控玩家")
    pipe = CommandPipeline(engine)
    pipe.compile_line("[global.main_player=主控玩家]")

    bridge = LLMAgentBridge(FakeClient())  # type: ignore[arg-type]
    for _ in bridge.run_step_stream(
        pipeline=pipe,
        recent_user_turns=["User: 开始", "System: 开场"],
        current_user_input="我下一张地狱飞龙",
        apply_commands=True,
    ):
        pass

    # 地狱飞龙 cost=4, so from 10 -> 6 after auto flush deploy execution.
    assert_true(abs(main.holy_water - 6.0) < 1e-9, "deploy should deduct holy water via auto queue flush")
    print("PASS: narrative queue flush test")


if __name__ == "__main__":
    main()

