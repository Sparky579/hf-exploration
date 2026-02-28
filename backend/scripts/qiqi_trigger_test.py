"""
Module purpose:
- Verify the scripted trigger:
  - time 8, if 许琪琪 is not in main player's team, she dies by skeletons.

Checks:
1. Not invited -> profile status becomes 死亡 after time > 8.
2. Invited -> profile status stays 存活 after time > 8.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend import GameEngine, GlobalConfig, PlayerRole, build_default_campus_map


def assert_true(cond: bool, message: str) -> None:
    if not cond:
        raise AssertionError(message)


def build_engine() -> GameEngine:
    campus = build_default_campus_map()
    cfg = GlobalConfig()
    engine = GameEngine(campus, cfg)
    p1 = PlayerRole("主控玩家", campus, cfg, "东教学楼内部")
    engine.register_player(p1)
    engine.set_main_player("主控玩家")
    return engine


def main() -> None:
    # Case 1: not invited -> dies.
    e1 = build_engine()
    e1.advance_time(8.5)
    status1 = e1.get_character_profile("许琪琪").status
    assert_true(status1 == "死亡", "许琪琪 should die when not invited by time > 8")

    # Case 2: invited -> survives.
    e2 = build_engine()
    e2.set_companion_in_team("许琪琪", True)
    e2.advance_time(8.5)
    status2 = e2.get_character_profile("许琪琪").status
    assert_true(status2 == "存活", "许琪琪 should survive when already in team")

    print("PASS: qiqi trigger test")


if __name__ == "__main__":
    main()
