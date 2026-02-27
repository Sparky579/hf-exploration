"""
Module purpose:
- Verify runtime fixes for:
  1) `character.<main_player>.deck` alias can set real player deck,
  2) spaced card names are normalized (e.g. "掘 地矿工"),
  3) hostile roles promoted to PlayerRole regenerate and consume holy-water rules.

Checks:
1. Promote enemy role to player runtime and confirm registration.
2. `character.主控玩家.deck=...` updates player deck without profile lookup error.
3. Main-player install gate blocks holy-water regen while enemy regen still works.
4. Battle+emergency multipliers apply to enemy holy-water regen.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend import CommandPipeline, GameEngine, GlobalConfig, PlayerRole, Role, build_default_campus_map


def assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected={expected!r}, actual={actual!r}")


def assert_close(actual: float, expected: float, message: str, eps: float = 1e-9) -> None:
    if abs(float(actual) - float(expected)) > eps:
        raise AssertionError(f"{message}: expected={expected!r}, actual={actual!r}")


def main() -> None:
    campus = build_default_campus_map()
    cfg = GlobalConfig()
    engine = GameEngine(campus, cfg)

    main_player = PlayerRole("主控玩家", campus, cfg, "东教学楼内部")
    engine.register_player(main_player)
    engine.set_main_player("主控玩家")

    Role("李再斌", campus, cfg, "宿舍")
    enemy_profile = engine.get_character_profile("李再斌")
    enemy_player = engine.promote_role_to_player("李再斌", card_deck=list(enemy_profile.card_deck), card_valid=4)
    assert_equal(enemy_player.name, "李再斌", "enemy should be promoted into player runtime")

    pipe = CommandPipeline(engine)

    # Alias command should update player deck, and card names with accidental spaces should be normalized.
    phone_deck = engine.get_character_profile("马超鹏").card_deck
    deck_line = ",".join(phone_deck).replace("掘地矿工", "掘 地矿工")
    pipe.compile_line(f"[character.主控玩家.deck={deck_line}]")
    assert_equal(main_player.card_deck[6], "掘地矿工", "spaced card name should be normalized")

    pipe.compile_line("[global.main_game_state=not_installed]")
    engine.advance_time(2.0)
    assert_close(main_player.holy_water, 0.0, "main player should stay 0 when game not installed")
    assert_close(enemy_player.holy_water, 1.0, "enemy player should still regenerate at base rate")

    pipe.compile_line("[global.battle=李再斌]")
    pipe.compile_line("[global.emergency=true]")
    engine.advance_time(1.0)
    assert_close(enemy_player.holy_water, 5.0, "enemy should gain +4 in battle+emergency")
    assert_close(main_player.holy_water, 0.0, "main install gate should still clamp holy water")

    print("PASS: enemy runtime state test")


if __name__ == "__main__":
    main()
