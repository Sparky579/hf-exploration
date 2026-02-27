"""
Module purpose:
- Local smoke test script for core backend systems.

Functions:
- assert_equal(actual, expected, message): minimal assertion helper.
- test_parallel_movement(engine, p1, p2): movement is queued and resolved by global time.
- test_holy_water_regen(engine, cfg, p1): 1x/2x/4x/8x holy-water rates.
- test_wartime_units_cleanup(engine, cfg, p1): wartime units are removed after battle.
- test_dynamic_states(engine, cfg, p1): global/role dynamic state APIs.
- test_deck_rotation_and_consume(p1): deploy cost and deck rotation.
- main(): build objects, run all checks, print PASS if all pass.
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
    engine.advance_time(1)
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
    p1.holy_water = 100
    persistent = p1.deploy_unit("巨人")
    engine.set_battle_phase(True)
    wartime = p1.deploy_unit("骷髅军团")
    engine.set_battle_phase(False)
    assert_equal(persistent.unit_id in p1.active_units, True, "non-wartime should stay")
    assert_equal(wartime.unit_id in p1.active_units, False, "wartime should be removed")


def test_dynamic_states(engine: GameEngine, cfg: GlobalConfig, p1: PlayerRole) -> None:
    global_text = "全局动态：今日下雨"
    role_text = "角色动态：正在警戒"
    engine.add_global_dynamic_state(global_text)
    engine.add_role_dynamic_state("P1", role_text)
    assert_equal(global_text in cfg.list_dynamic_states(), True, "global dynamic state should exist")
    assert_equal(role_text in p1.list_dynamic_states(), True, "role dynamic state should exist")


def test_deck_rotation_and_consume(p1: PlayerRole) -> None:
    p1.holy_water = 100
    before_top = p1.card_deck[0]
    card_cost = p1.available_cards[before_top].consume
    p1.deploy_from_deck()
    assert_equal(p1.card_deck[-1], before_top, "deck rotation failed")
    assert_equal(p1.holy_water, 100 - card_cost, "holy water consume failed")


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
    test_dynamic_states(engine, cfg, p1)
    test_deck_rotation_and_consume(p1)
    print("PASS: backend smoke tests")


if __name__ == "__main__":
    main()
