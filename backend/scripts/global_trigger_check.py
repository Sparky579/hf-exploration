"""
Module purpose:
- Check whether global story events are triggered as time advances.

This script uses command pipeline commands to drive time flow and map damage,
then prints trigger states and validates expected transitions.
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
    engine.register_player(p1)
    pipeline = CommandPipeline(engine)

    pipeline.compile_line("global.main_player=P1")
    assert_true(not engine.event_checker.is_triggered("alert"), "alert should start as false")
    assert_true(not engine.event_checker.is_triggered("emergency"), "emergency should start as false")

    pipeline.compile_line("time.advance=8")
    assert_true(not engine.event_checker.is_triggered("alert"), "alert must require strictly > trigger time")

    pipeline.compile_line("time.advance=0.5")
    assert_true(engine.event_checker.is_triggered("alert"), "alert should trigger at time > 8")

    pipeline.compile_line("map.德政楼.valid=false")
    pipeline.compile_line("time.advance=0.5")
    assert_true(engine.event_checker.is_triggered("emergency"), "emergency should trigger after 德政楼 destroyed + time check")
    assert_true(cfg.is_emergency_phase, "global emergency phase should be enabled")

    # Explosion should trigger after emergency start + 6 time units (strictly >).
    pipeline.compile_line("time.advance=6")
    assert_true(not engine.event_checker.is_triggered("explosion"), "explosion must require strictly > deadline")
    pipeline.compile_line("time.advance=0.5")
    assert_true(engine.event_checker.is_triggered("explosion"), "explosion should trigger after deadline")
    print("PASS: global trigger check")


if __name__ == "__main__":
    main()
