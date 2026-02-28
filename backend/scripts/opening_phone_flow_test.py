"""
Module purpose:
- Verify deterministic opening phone flow for hotspot branch.

Functions:
- assert_true(cond, message): minimal assertion helper.
- build_engine(): create runtime with one main player.
- main(): run two checks:
  1) t>=2 should create 马超鹏 notice dynamic state on hotspot branch.
  2) t>=3 with unavailable main phone should auto handoff 马超鹏 backup phone,
     switch main deck, and set main_game_state to installed.
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
    engine = build_engine()
    engine.add_global_dynamic_state("开场分支:借马超鹏热点更新")
    engine.set_main_game_state("confiscated")

    # t=2 notice
    engine.advance_time(1.0)
    states = set(engine.global_config.dynamic_states)
    assert_true(
        "开场事件:马超鹏已在课堂提醒他也注意到了更新" in states,
        "hotspot branch should add t>=2 notice marker",
    )

    # t=3 handoff
    engine.advance_time(1.0)
    states = set(engine.global_config.dynamic_states)
    assert_true(
        "开场事件:马超鹏已主动交付主手机" in states,
        "hotspot branch should handoff backup phone at t>=3 when phone unavailable",
    )
    assert_true(
        "开场事件:主控已持有马超鹏主手机" in states,
        "main-player-held-main-phone marker should exist after handoff",
    )
    assert_true(
        engine.global_config.main_game_state == "installed",
        "main_game_state should become installed after backup handoff",
    )
    main = engine.get_player("主控玩家")
    ma_deck = engine.get_companion_profile("马超鹏").deck
    assert_true(main.card_deck == ma_deck, "main player deck should switch to 马超鹏 deck")
    assert_true(abs(main.holy_water - 0.0) < 1e-9, "holy water should reset to 0 on handoff")

    print("PASS: opening phone flow test")


if __name__ == "__main__":
    main()
