"""
Module purpose:
- Verify main-player holy-water state machine:
  - only `installed` can regenerate holy water,
  - non-installed states force holy water to stay at 0.

Checks:
1. installed -> holy water regenerates normally.
2. downloading/not_installed/confiscated -> holy water is zero and cannot increase.
3. switching back to installed resumes regeneration.
4. command aliases (`global.phone_state` / `global.client_state`) work.
5. `+=` cannot bypass the state-machine gate.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend import CommandPipeline, GameEngine, GlobalConfig, PlayerRole, build_default_campus_map


def assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected={expected!r}, actual={actual!r}")


def main() -> None:
    campus = build_default_campus_map()
    cfg = GlobalConfig()
    engine = GameEngine(campus, cfg)
    start_node = list(campus.nodes.keys())[0]
    p1 = PlayerRole("MAIN", campus, cfg, start_node)
    engine.register_player(p1)
    engine.set_main_player("MAIN")
    pipe = CommandPipeline(engine)

    pipe.compile_line("[global.main_player=MAIN]")

    pipe.compile_line("[global.main_game_state=installed]")
    p1.holy_water = 0.0
    engine.advance_time(2.0)
    assert_equal(p1.holy_water, 1.0, "installed state should regenerate holy water")

    for state in ("downloading", "not_installed", "confiscated"):
        pipe.compile_line(f"[global.main_game_state={state}]")
        # Even if user tries to set holy water, system should clamp to 0.
        pipe.compile_line("[MAIN.holy_water=9]")
        assert_equal(p1.holy_water, 0.0, f"{state} should force holy water to zero")
        pipe.compile_line("[MAIN.holy_water+=1]")
        assert_equal(p1.holy_water, 0.0, f"{state} should block += holy water")
        engine.advance_time(2.0)
        assert_equal(p1.holy_water, 0.0, f"{state} should block regeneration")

    # Chinese alias should also work.
    pipe.compile_line("[global.main_game_state=已安装]")
    engine.advance_time(2.0)
    assert_equal(p1.holy_water, 1.0, "switching back to installed should resume regeneration")

    # Field aliases should work.
    pipe.compile_line("[global.phone_state=下载中]")
    engine.advance_time(2.0)
    assert_equal(p1.holy_water, 0.0, "phone_state alias should map to main_game_state")

    pipe.compile_line("[global.client_state=installed]")
    engine.advance_time(2.0)
    assert_equal(p1.holy_water, 1.0, "client_state alias should map to main_game_state")

    print("PASS: holy water install-state test")


if __name__ == "__main__":
    main()
