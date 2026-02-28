"""
Module purpose:
- Verify `scene_event.trigger=<id>` command behavior.

Checks:
1. Triggering `east_toilet_yanhongfan_encounter` sets global/role battle targets.
2. One-shot marker is added into global dynamic states.
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
    Role("颜宏帆", campus, cfg, "东教学楼内部")

    pipe = CommandPipeline(engine)
    pipe.compile_line("[global.main_player=主控玩家]")
    pipe.compile_line("[scene_event.trigger=east_toilet_yanhongfan_encounter]")

    assert_true(engine.global_config.battle_state == "颜宏帆", "global battle target mismatch")
    assert_true(engine.get_role("主控玩家").battle_target == "颜宏帆", "main role battle target mismatch")
    assert_true(engine.get_role("颜宏帆").battle_target == "主控玩家", "enemy role battle target mismatch")
    assert_true(
        "场景事件:厕所遭遇颜宏帆已触发" in engine.global_config.dynamic_states,
        "missing one-shot scene event marker",
    )

    print("PASS: scene event command test")


if __name__ == "__main__":
    main()

