"""
Module purpose:
- Verify hard auto-awareness rule after t>5 for enemy/neutral same-node encounters.

Checks:
1. At t<=5, no auto memory marker is written.
2. At t>5 and same node with neutral/enemy role, marker `遭遇<name>` is auto-written.
3. Repeated ticks should not duplicate the same marker.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend import CommandPipeline, GameEngine, GlobalConfig, PlayerRole, Role, build_default_campus_map


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
    Role("黎诺存", campus, cfg, "西教学楼南")

    pipe = CommandPipeline(engine)
    pipe.compile_line("[global.main_player=主控玩家]")

    # Move to same node with 黎诺存 at t<=5.
    pipe.compile_line("[主控玩家.location=西教学楼南]")
    assert_true("遭遇黎诺存" not in engine.global_config.dynamic_states, "should not auto-detect at t<=5")

    # Time passes to >5: auto awareness should be added.
    pipe.compile_line("[time.advance=6]")
    assert_true("遭遇黎诺存" in engine.global_config.dynamic_states, "missing auto encounter marker after t>5")
    assert_true("遭遇黎诺存" in engine.get_role("主控玩家").dynamic_states, "missing main role memory marker")

    # No duplication on repeated checks.
    before_count = sum(1 for x in engine.global_config.dynamic_states if x == "遭遇黎诺存")
    pipe.compile_line("[time.advance=1]")
    after_count = sum(1 for x in engine.global_config.dynamic_states if x == "遭遇黎诺存")
    assert_true(before_count == after_count == 1, "encounter marker should not duplicate")

    print("PASS: auto encounter awareness test")


if __name__ == "__main__":
    main()

