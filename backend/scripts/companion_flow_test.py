"""
Module purpose:
- Integration test for companion discovery/invite/affection/move-cost mechanics.

This test intentionally drives the system through CommandPipeline commands only.
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

    # Set main player and recruit 罗宾（auto discover in 田径场）.
    pipeline.compile_line("global.main_player=P1")
    pipeline.compile_line("P1.location=田径场")
    pipeline.compile_line("P1.invite=罗宾")
    assert_true("罗宾" in cfg.list_team_companions(), "罗宾 should join team")
    assert_true(abs(cfg.get_effective_main_move_cost(1.0) - 1.5) < 1e-9, "罗宾 should set move cost to 1.5")

    # Verify move cost 1.5 by queue move + time.
    pipeline.compile_line("P1.move=小卖部")
    pipeline.compile_line("queue.flush=true")
    pipeline.compile_line("time.advance=1")
    assert_true(p1.current_location == "田径场", "1.0 time should not finish 1.5 move")
    pipeline.compile_line("time.advance=0.5")
    assert_true(p1.current_location == "小卖部", "1.5 time should finish move")

    # 许琪琪: unavailable in [6,9].
    pipeline.compile_line("P1.location=东教学楼内部")
    pipeline.compile_line("time.advance=5")  # current time now 6.5
    failed = False
    try:
        pipeline.compile_line("P1.discover=许琪琪")
    except ValueError:
        failed = True
    assert_true(failed, "许琪琪 should be undiscoverable during [6,9]")

    pipeline.compile_line("time.advance=3")  # now 9.5
    pipeline.compile_line("P1.discover=许琪琪")
    pipeline.compile_line("P1.invite=许琪琪")
    assert_true("许琪琪" in cfg.list_team_companions(), "许琪琪 should join team")
    assert_true(abs(cfg.get_effective_main_move_cost(1.0) - 2.0) < 1e-9, "许琪琪 should set move cost to 2")

    # Romance affection naturally increases with time.
    affection_before = cfg.get_companion_state("许琪琪")["affection"]
    pipeline.compile_line("time.advance=2")
    affection_after = cfg.get_companion_state("许琪琪")["affection"]
    assert_true(abs((affection_after - affection_before) - 2.0) < 1e-9, "romance affection should grow by time")

    # Invite 冬雨: existing romance (许琪琪) should leave.
    pipeline.compile_line("P1.location=图书馆")
    pipeline.compile_line("P1.discover=冬雨")
    pipeline.compile_line("P1.invite=冬雨")
    team = cfg.list_team_companions()
    assert_true("冬雨" in team, "冬雨 should join team")
    assert_true("许琪琪" not in team, "existing romance companion should leave when new romance joins")

    # 马超鹏: force discover by command then invite; deck should switch.
    pipeline.compile_line("companion.马超鹏.discovered=true")
    pipeline.compile_line("P1.invite=马超鹏")
    assert_true(p1.card_deck == engine.get_companion_profile("马超鹏").deck, "main player deck should switch")

    # Global team fixed-format operations + affection commands.
    pipeline.compile_line("global.team=罗宾,冬雨")
    assert_true(set(cfg.list_team_companions()) == {"罗宾", "冬雨"}, "global.team replace should work")
    pipeline.compile_line("companion.冬雨.affection=3")
    pipeline.compile_line("companion.冬雨.affection+=2")
    pipeline.compile_line("companion.冬雨.affection-=1")
    assert_true(abs(cfg.get_companion_state("冬雨")["affection"] - 4.0) < 1e-9, "companion affection commands should work")

    # Two hostile noticers trigger jealousy dynamic state.
    pipeline.compile_line("companion.许琪琪.noticed_by+=李再斌")
    pipeline.compile_line("companion.许琪琪.noticed_by+=颜宏帆")
    assert_true(
        "两名敌对角色因注意到许琪琪而吃醋愤怒" in cfg.list_dynamic_states(),
        "jealousy dynamic state should be added",
    )

    print("PASS: companion flow tests")


if __name__ == "__main__":
    main()
