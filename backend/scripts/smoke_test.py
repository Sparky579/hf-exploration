"""
Module purpose:
- Local smoke test script for the backend game system.

Functions:
- assert_equal(actual, expected, message): minimal assertion helper.
- test_parallel_movement(engine, p1, p2): verify movement is queued and resolved together by global time.
- test_holy_water_regen(engine, cfg, p1): verify 1x/2x/4x/8x holy-water rates.
- test_wartime_units_cleanup(engine, cfg, p1): verify wartime units are removed after battle ends.
- test_target_selection(p1): verify target-priority and manual-target rules.
- main(): build objects, run all tests, print PASS if all checks pass.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend import GameEngine, GlobalConfig, PlayerRole, build_default_campus_map


def assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected={expected!r}, actual={actual!r}")


def test_parallel_movement(engine: GameEngine, p1: PlayerRole, p2: PlayerRole) -> None:
    engine.issue_move("P1", "南教学楼")
    engine.issue_move("P2", "图书馆")
    assert_equal((p1.current_location, p2.current_location), ("东教学楼南", "西教学楼南"), "move should be queued")
    engine.advance_time(0.5)
    assert_equal((p1.current_location, p2.current_location), ("南教学楼", "图书馆"), "parallel move result")


def test_holy_water_regen(engine: GameEngine, cfg: GlobalConfig, p1: PlayerRole) -> None:
    cases = [
        (False, False, 2, 1.0),
        (True, False, 1, 1.0),
        (False, True, 1, 2.0),
        (True, True, 1, 4.0),
    ]
    for emergency, battle, dt, expected in cases:
        cfg.current_time_unit = 0
        p1.holy_water = 0
        cfg.set_state("emergency", emergency)
        cfg.set_state("battle", battle)
        engine.advance_time(dt)
        assert_equal(p1.holy_water, expected, "holy water regen mismatch")


def test_wartime_units_cleanup(engine: GameEngine, cfg: GlobalConfig, p1: PlayerRole) -> None:
    cfg.set_state("battle", False)
    persistent = p1.deploy_unit("巨人")
    engine.set_battle_phase(True)
    wartime = p1.deploy_unit("骷髅军团")
    engine.set_battle_phase(False)
    assert_equal(persistent.unit_id in p1.active_units, True, "non-wartime should stay")
    assert_equal(wartime.unit_id in p1.active_units, False, "wartime should be removed")


def test_target_selection(p1: PlayerRole) -> None:
    giant = p1.deploy_unit("巨人")
    kind, target_id = p1.select_attack_target(
        giant.unit_id,
        enemy_unit_ids=["eu1"],
        enemy_building_ids=["eb1"],
        enemy_npc_ids=["npc1"],
        field_building_ids=["fb1"],
    )
    assert_equal((kind, target_id), ("enemy_building", "eb1"), "giant should prefer building")

    kind2, target_id2 = p1.select_attack_target(
        giant.unit_id,
        enemy_unit_ids=[],
        enemy_building_ids=[],
        enemy_npc_ids=["npc1"],
        field_building_ids=["fb1"],
        manual_target_id="npc1",
        manual_target_kind="enemy_npc",
    )
    assert_equal((kind2, target_id2), ("enemy_npc", "npc1"), "manual target when combat targets are empty")


def main() -> None:
    campus = build_default_campus_map()
    cfg = GlobalConfig()
    engine = GameEngine(campus, cfg)
    p1 = PlayerRole("P1", campus, cfg, "东教学楼南")
    p2 = PlayerRole("P2", campus, cfg, "西教学楼南")
    engine.register_player(p1)
    engine.register_player(p2)

    test_parallel_movement(engine, p1, p2)
    test_holy_water_regen(engine, cfg, p1)
    test_wartime_units_cleanup(engine, cfg, p1)
    test_target_selection(p1)
    print("PASS: backend smoke tests")


if __name__ == "__main__":
    main()
