"""
Module purpose:
- Verify scene-event prompting context generation.

Checks:
1. At t<=5 and in 东教学楼内部 -> scene event candidate should be present.
2. Candidate includes `scene_event.trigger=<id>` command hint for model-side decision.
3. At t>5 -> scene event candidate should not be present.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend import CommandPipeline, GameEngine, GlobalConfig, PlayerRole, Role, build_default_campus_map
from backend.state_snapshot import build_step_context


def assert_true(cond: bool, message: str) -> None:
    if not cond:
        raise AssertionError(message)


def build_runtime() -> tuple[GameEngine, CommandPipeline]:
    campus = build_default_campus_map()
    cfg = GlobalConfig()
    engine = GameEngine(campus, cfg)
    main = PlayerRole("主控玩家", campus, cfg, "东教学楼内部")
    engine.register_player(main)
    engine.set_main_player("主控玩家")
    Role("颜宏帆", campus, cfg, "东教学楼内部")
    pipe = CommandPipeline(engine)
    pipe.compile_line("[global.main_player=主控玩家]")
    return engine, pipe


def main() -> None:
    # Case 1: candidate exists.
    e1, p1 = build_runtime()
    c1 = build_step_context(
        engine=e1,
        pipeline=p1,
        recent_user_turns=["User: 开始", "System: 开场"],
        current_user_input="去东教学楼南",
    )
    events1 = c1.get("scene_events", [])
    assert_true(bool(events1), "scene_events candidate should exist at t<=5")
    assert_true(
        str(events1[0].get("id", "")) == "east_toilet_yanhongfan_encounter",
        "unexpected scene event id",
    )
    assert_true(
        str(events1[0].get("trigger_command", "")) == "[scene_event.trigger=east_toilet_yanhongfan_encounter]",
        "missing scene event trigger command hint",
    )

    # Case 3: time window passed.
    e3, p3 = build_runtime()
    p3.compile_line("[time.advance=5]")
    c3 = build_step_context(
        engine=e3,
        pipeline=p3,
        recent_user_turns=["User: 开始", "System: 开场"],
        current_user_input="我原地搜查一下",
    )
    assert_true(not c3.get("scene_events", []), "scene event should not trigger when t>5")

    print("PASS: scene event prompt test")


if __name__ == "__main__":
    main()
