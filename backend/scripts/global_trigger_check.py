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

    # Alert is based on absolute world time (> 8), while runtime may start at t=1.
    start_time = float(engine.global_config.current_time_unit)
    threshold = float(engine.story_setting.alert_trigger_time)
    to_deadline = threshold - start_time
    if to_deadline > 0:
        pipeline.compile_line(f"time.advance={to_deadline:g}")
    assert_true(
        not engine.event_checker.is_triggered("alert"),
        f"alert must require strictly > trigger time (now={engine.global_config.current_time_unit}, threshold={threshold})",
    )

    pipeline.compile_line("time.advance=0.5")
    assert_true(engine.event_checker.is_triggered("alert"), "alert should trigger at time > threshold")

    pipeline.compile_line("map.德政楼.valid=false")
    pipeline.compile_line("time.advance=0.5")
    assert_true(engine.event_checker.is_triggered("emergency"), "emergency should trigger after 德政楼 destroyed + time check")
    assert_true(cfg.is_emergency_phase, "global emergency phase should be enabled")

    # Explosion should trigger at emergency start + 6 time units (>= deadline).
    pipeline.compile_line("time.advance=6")
    assert_true(engine.event_checker.is_triggered("explosion"), "explosion should trigger at deadline")
    print("PASS: global trigger check")


if __name__ == "__main__":
    main()
