"""
Module purpose:
- Integration test for the text command pipeline.

Functions:
- assert_true(cond, message): minimal assertion helper.
- main(): build game world, compile pipeline script, verify queue/state behavior.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend import CommandPipeline, GameEngine, GlobalConfig, PlayerRole, build_default_campus_map


def assert_true(cond: bool, message: str) -> None:
    if not cond:
        raise AssertionError(message)


def main() -> None:
    campus = build_default_campus_map()
    cfg = GlobalConfig()
    engine = GameEngine(campus, cfg)
    p1 = PlayerRole("P1", campus, cfg, "东教学楼南")
    p2 = PlayerRole("P2", campus, cfg, "西教学楼南")
    engine.register_player(p1)
    engine.register_player(p2)
    pipeline = CommandPipeline(engine)

    script = """
    # immediate state changes
    P1.location=正门
    P1.health=8
    P1.holy_water=20
    P1.holy_water+=1
    P1.holy_water-=0.5
    P1.health-=1
    P1.card_valid=4
    P1.card_valid+=1
    global.state+=全局动态：演练开始
    P1.state+=角色动态：进入战备
    P1.nearby_units=地狱飞龙:full,巨人:damaged
    P1.nearby_unit.巨人=dead

    # queue move/deploy
    P1.move=东教学楼南
    P1.deploy=地狱飞龙
    queue.flush=true

    # progress world and change phase
    time.advance=1
    global.battle=true
    time.advance=0.5

    # runtime unit state
    P1.unit.P1-U1.health=50
    P1.unit.P1-U1.health=0
    """
    pipeline.compile_script(script)

    assert_true(p1.current_location == "东教学楼南", "move should be completed after 1 time unit")
    assert_true(p1.health == 7, "role health +=/-= should be updated")
    assert_true(p1.card_valid == 5, "card_valid += should be updated")
    assert_true(abs(p1.holy_water - 18.0) < 1e-9, "holy_water +=/-= and regen should be consistent")
    assert_true("全局动态：演练开始" in cfg.list_dynamic_states(), "global dynamic text missing")
    assert_true("角色动态：进入战备" in p1.list_dynamic_states(), "role dynamic text missing")
    assert_true("巨人" not in p1.list_nearby_units(), "dead nearby unit should be removed")
    assert_true("地狱飞龙" in p1.card_deck[-1], "deck should rotate after deploy")
    assert_true("P1-U1" not in p1.active_units, "unit should be removed after health set to 0")
    assert_true(cfg.is_battle_phase, "battle phase should be true")
    assert_true(abs(cfg.current_time_unit - 1.5) < 1e-9, "time should be 1.5")
    assert_true(len(pipeline.message_queue) == 0, "queue should be empty after flush")
    print("PASS: backend pipeline tests")


if __name__ == "__main__":
    main()
