"""
Module purpose:
- Simulate a complete game progression using only CommandPipeline commands.

Scenario:
- Main player starts in campus.
- Alert triggers after time > 8.
- 德政楼 destroyed triggers emergency and blast countdown.
- 国际部 is destroyed during emergency, so that escape route is unavailable.
- Main player fails to escape before explosion and dies -> game over.
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

    # Full run: only pipeline commands are used for state changes.
    script = """
    global.main_player=P1
    P1.holy_water=20
    P1.health=10
    P1.location=国际部
    time.advance=8.5
    map.德政楼.valid=false
    time.advance=0.5
    map.国际部.valid=false
    time.advance=6.5
    """
    pipeline.compile_script(script)

    assert_true(engine.event_checker.is_triggered("alert"), "alert should be triggered")
    assert_true(engine.event_checker.is_triggered("emergency"), "emergency should be triggered")
    assert_true(engine.event_checker.is_triggered("explosion"), "explosion should be triggered")
    assert_true(engine.game_over, "game should be over when main player dies")
    assert_true(engine.game_result == "main_player_dead", "game result should be main_player_dead")
    assert_true(p1.health <= 0, "main player should be dead")

    # Verify 国际部 escape is blocked after it is destroyed in emergency window.
    blocked = False
    try:
        pipeline.compile_line("P1.escape=国际部")
    except ValueError:
        blocked = True
    assert_true(blocked, "international department escape should be blocked when node is destroyed")

    print("PASS: story full game simulation")


if __name__ == "__main__":
    main()
