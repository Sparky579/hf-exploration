"""
Module purpose:
- Verify predefined game-event trigger for download/install flow.

Checks:
1. own-phone install event: auto +2 time, main_game_state=installed, holy_water=0, card_valid=4.
2. ma-phone install event: requires marker and applies the same fixed effects.
3. international teacher reveal event when installed: uninstall is applied (phone remains with player).
4. international teacher reveal event when not installed: dialog only (no uninstall), and international exit is blocked.
5. Killing 信息老师 beforehand should prevent the event and keep international escape available.
6. 食堂李秦彬提醒事件: consumes 1.5 time and grants main-phone token (card_valid=8).
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


def build_runtime() -> tuple[GameEngine, CommandPipeline, PlayerRole]:
    campus = build_default_campus_map()
    cfg = GlobalConfig()
    engine = GameEngine(campus, cfg)
    main = PlayerRole("主控玩家", campus, cfg, "东教学楼内部")
    engine.register_player(main)
    engine.set_main_player("主控玩家")
    pipe = CommandPipeline(engine)
    pipe.compile_line("[global.main_player=主控玩家]")
    return engine, pipe, main


def main() -> None:
    # Case 1: own phone
    e1, p1, main1 = build_runtime()
    p1.compile_line("[global.main_game_state=not_installed]")
    main1.holy_water = 9.0
    main1.set_card_valid(6)
    t0 = float(e1.global_config.current_time_unit)
    p1.compile_line("[game_event.trigger=install_update_game_with_own_phone]")
    assert_true(abs(e1.global_config.current_time_unit - (t0 + 2.0)) < 1e-9, "event should auto advance 2 time")
    assert_true(e1.global_config.main_game_state == "installed", "main_game_state should be installed")
    assert_true(abs(main1.holy_water - 0.0) < 1e-9, "holy water should reset to 0")
    assert_true(main1.card_valid == 4, "card_valid should be reset to 4")

    # Case 2: 马超鹏主手机
    e2, p2, main2 = build_runtime()
    p2.compile_line("[global.main_game_state=confiscated]")
    p2.compile_line("[global.state+=开场事件:主控已持有马超鹏主手机]")
    main2.holy_water = 8.0
    main2.set_card_valid(7)
    t1 = float(e2.global_config.current_time_unit)
    p2.compile_line("[game_event.trigger=install_update_game_with_ma_phone]")
    assert_true(abs(e2.global_config.current_time_unit - (t1 + 2.0)) < 1e-9, "ma-phone event should auto advance 2 time")
    assert_true(e2.global_config.main_game_state == "installed", "main_game_state should be installed")
    assert_true(abs(main2.holy_water - 0.0) < 1e-9, "holy water should reset to 0")
    assert_true(main2.card_valid == 4, "card_valid should be reset to 4")

    # Case 3: international teacher reveal branch (installed -> uninstall only).
    e3, p3, main3 = build_runtime()
    p3.compile_line("[global.main_game_state=installed]")
    main3.holy_water = 6.0
    main3.set_card_valid(4)
    p3.compile_line("[主控玩家.location=国际部]")
    p3.compile_line("[scene_event.trigger=international_it_teacher_encounter]")
    t2 = float(e3.global_config.current_time_unit)
    p3.compile_line("[game_event.trigger=international_it_teacher_reveal_confiscate]")
    assert_true(abs(e3.global_config.current_time_unit - (t2 + 2.0)) < 1e-9, "teacher reveal should advance 2 time")
    assert_true("场景事件:国际部信息老师已结局" in e3.global_config.dynamic_states, "missing event done marker")
    assert_true("场景事件:国际部信息老师卸载游戏" in e3.global_config.dynamic_states, "missing uninstall marker")
    assert_true("场景事件:国际部信息老师封锁国际部出口" in e3.global_config.dynamic_states, "missing intl exit blocked marker")
    assert_true(e3.global_config.main_game_state == "not_installed", "reveal branch should force not_installed")
    assert_true(abs(main3.holy_water - 0.0) < 1e-9, "holy water should be zero after reveal branch")
    assert_true(main3.card_valid == 0, "card_valid should be zero after reveal branch")
    assert_true(not main3.active_units, "main player units should be cleared after reveal branch")

    # Case 4: international teacher reveal branch when not installed -> warning dialog only.
    e4, p4, main4 = build_runtime()
    p4.compile_line("[global.main_game_state=not_installed]")
    p4.compile_line("[主控玩家.location=国际部]")
    p4.compile_line("[scene_event.trigger=international_it_teacher_encounter]")
    t3 = float(e4.global_config.current_time_unit)
    p4.compile_line("[game_event.trigger=international_it_teacher_reveal_confiscate]")
    assert_true(abs(e4.global_config.current_time_unit - (t3 + 2.0)) < 1e-9, "teacher dialog branch should advance 2 time")
    assert_true("场景事件:国际部信息老师已结局" in e4.global_config.dynamic_states, "missing event done marker (dialog branch)")
    assert_true(
        "场景事件:国际部信息老师卸载游戏" not in e4.global_config.dynamic_states,
        "should not uninstall when game is not installed",
    )
    assert_true("场景事件:国际部信息老师封锁国际部出口" in e4.global_config.dynamic_states, "missing intl exit blocked marker")
    assert_true(e4.global_config.main_game_state == "not_installed", "game state should remain not_installed")
    escape_blocked = False
    try:
        p4.compile_line("[主控玩家.escape=国际部]")
    except ValueError:
        escape_blocked = True
    assert_true(escape_blocked, "international escape should be blocked by information teacher")

    # Case 5: kill 信息老师 first -> event unavailable and no出口封锁.
    e5, p5, _main5 = build_runtime()
    p5.compile_line("[主控玩家.location=国际部]")
    p5.compile_line("[character.信息老师.status=死亡]")
    teacher_event_blocked = False
    try:
        p5.compile_line("[scene_event.trigger=international_it_teacher_encounter]")
    except ValueError:
        teacher_event_blocked = True
    assert_true(teacher_event_blocked, "international teacher event should not trigger after teacher death")
    # International escape should remain available (before alert and no blocker marker).
    p5.compile_line("[主控玩家.escape=国际部]")

    # Case 6: canteen remind -> +1.5 time, token active, main card_valid=8.
    e6, p6, main6 = build_runtime()
    p6.compile_line("[global.main_game_state=installed]")
    p6.compile_line("[主控玩家.location=食堂]")
    p6.compile_line("[scene_event.trigger=canteen_liqinbin_prompt]")
    t4 = float(e6.global_config.current_time_unit)
    p6.compile_line("[game_event.trigger=canteen_liqinbin_remind_and_token]")
    assert_true(abs(e6.global_config.current_time_unit - (t4 + 1.5)) < 1e-9, "canteen remind should advance 1.5 time")
    assert_true("场景事件:食堂李秦彬提醒已完成" in e6.global_config.dynamic_states, "missing canteen done marker")
    assert_true("主控手机效果:皇室令牌已激活" in e6.global_config.dynamic_states, "missing main token marker")
    assert_true(main6.card_valid == 8, "main phone token should set main card_valid to 8")

    print("PASS: game event trigger test")


if __name__ == "__main__":
    main()
