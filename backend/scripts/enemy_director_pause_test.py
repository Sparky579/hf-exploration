"""
Smoke test for deterministic enemy director pause/resume behavior.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend import GameEngine, GlobalConfig, PlayerRole, Role, build_default_campus_map


MAIN = "\u4e3b\u63a7\u73a9\u5bb6"
LI = "\u674e\u518d\u658c"
YAN = "\u989c\u5b8f\u5e06"

EAST_INSIDE = "\u4e1c\u6559\u5b66\u697c\u5185\u90e8"
EAST_SOUTH = "\u4e1c\u6559\u5b66\u697c\u5357"
DORM = "\u5bbf\u820d"


def assert_close(actual: float, expected: float, message: str, eps: float = 1e-9) -> None:
    if abs(float(actual) - float(expected)) > eps:
        raise AssertionError(f"{message}: expected={expected!r}, actual={actual!r}")


def main() -> None:
    campus = build_default_campus_map()
    cfg = GlobalConfig()
    engine = GameEngine(campus, cfg)

    main_player = PlayerRole(MAIN, campus, cfg, EAST_INSIDE)
    engine.register_player(main_player)
    engine.set_main_player(MAIN)

    Role(LI, campus, cfg, DORM)
    Role(YAN, campus, cfg, EAST_INSIDE)

    li_profile = engine.get_character_profile(LI)
    yan_profile = engine.get_character_profile(YAN)
    engine.promote_role_to_player(LI, card_deck=list(li_profile.card_deck), card_valid=4)
    engine.promote_role_to_player(YAN, card_deck=list(yan_profile.card_deck), card_valid=4)

    engine.advance_time(1.0)
    snap = engine.enemy_director.snapshot()
    assert_close(snap[LI]["remaining_time"], 5.0, "li countdown should progress normally")
    assert_close(snap[YAN]["remaining_time"], 2.0, "yan countdown should pause on same-node start")
    if snap[YAN]["paused_reason"] != "same_node_with_main":
        raise AssertionError(f"yan pause reason mismatch: {snap[YAN]['paused_reason']}")

    engine.set_role_location(MAIN, EAST_SOUTH)
    engine.advance_time(1.0)
    snap = engine.enemy_director.snapshot()
    assert_close(snap[YAN]["remaining_time"], 1.0, "yan countdown should resume after separation")

    before = float(snap[LI]["remaining_time"])
    engine.set_battle_state(LI)
    engine.advance_time(2.0)
    snap = engine.enemy_director.snapshot()
    assert_close(snap[LI]["remaining_time"], before, "li countdown should pause while in battle")
    if snap[LI]["paused_reason"] != "in_battle":
        raise AssertionError(f"li pause reason mismatch: {snap[LI]['paused_reason']}")

    engine.set_battle_state(None)
    engine.advance_time(1.0)
    snap = engine.enemy_director.snapshot()
    assert_close(snap[LI]["remaining_time"], before - 1.0, "li countdown should continue after battle")

    print("PASS: enemy director pause test")


if __name__ == "__main__":
    main()

