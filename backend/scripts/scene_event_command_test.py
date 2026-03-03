"""
Module purpose:
- Verify `scene_event.trigger=<id>` command behavior.

Checks:
1. Triggering `east_toilet_yanhongfan_encounter` sets global/role battle targets.
2. One-shot marker is added into global dynamic states.
3. Triggering `international_it_teacher_encounter` enters pending-decision state.
4. Triggering `south_building_chenluo_heal_encounter` heals main player and makes 陈洛 leave.
5. 德政楼蓝光装置：观察后，满足重型阈值的火力可触发摧毁事件。
6. 正门/后门保安会阻拦逃离；需先用足够战力突破防线。
7. 食堂李秦彬提醒事件可授予主控手机皇室令牌（card_valid=8）。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend import CommandPipeline, GameEngine, GlobalConfig, PlayerRole, Role, build_default_campus_map


def assert_true(cond: bool, message: str) -> None:
    if not cond:
        raise AssertionError(message)


def main() -> None:
    campus = build_default_campus_map()
    cfg = GlobalConfig()
    engine = GameEngine(campus, cfg)
    main = PlayerRole("主控玩家", campus, cfg, "东教学楼内部")
    engine.register_player(main)
    engine.set_main_player("主控玩家")
    Role("颜宏帆", campus, cfg, "东教学楼内部")
    Role("陈洛", campus, cfg, "南教学楼")

    pipe = CommandPipeline(engine)
    pipe.compile_line("[global.main_player=主控玩家]")
    pipe.compile_line("[scene_event.trigger=east_toilet_yanhongfan_encounter]")

    assert_true(engine.global_config.battle_state == "颜宏帆", "global battle target mismatch")
    assert_true(engine.get_role("主控玩家").battle_target == "颜宏帆", "main role battle target mismatch")
    assert_true(engine.get_role("颜宏帆").battle_target == "主控玩家", "enemy role battle target mismatch")
    assert_true(
        "场景事件:厕所遭遇颜宏帆已触发" in engine.global_config.dynamic_states,
        "missing one-shot scene event marker",
    )

    # International teacher encounter should only set pending marker.
    pipe.compile_line("[主控玩家.location=国际部]")
    pipe.compile_line("[scene_event.trigger=international_it_teacher_encounter]")
    assert_true(
        "场景事件:国际部信息老师待抉择" in engine.global_config.dynamic_states,
        "missing international teacher pending marker",
    )

    # Chenluo heal event should heal main player and remove 陈洛 runtime role.
    pipe.compile_line("[主控玩家.location=南教学楼]")
    hp_before = float(engine.get_role("主控玩家").health)
    pipe.compile_line("[scene_event.trigger=south_building_chenluo_heal_encounter]")
    hp_after = float(engine.get_role("主控玩家").health)
    assert_true(abs(hp_after - (hp_before + 3.0)) < 1e-9, "chenluo heal should increase main hp by 3")
    assert_true(
        "场景事件:南教学楼遭遇陈洛已触发" in engine.global_config.dynamic_states,
        "missing chenluo one-shot marker",
    )
    assert_true("陈洛" not in engine.campus_map.roles, "陈洛 should leave runtime scene after event")

    # Dezheng blue device event: discover marker, heavy required for destroy.
    pipe.compile_line("[主控玩家.location=德政楼]")
    pipe.compile_line("[scene_event.trigger=dezheng_blue_device_observation]")
    assert_true(
        "场景事件:德政楼蓝光装置已发现" in engine.global_config.dynamic_states,
        "missing dezheng device seen marker",
    )
    # Without heavy source, destroy should fail.
    failed = False
    try:
        pipe.compile_line("[game_event.trigger=destroy_dezheng_blue_device_with_heavy]")
    except Exception:
        failed = True
    assert_true(failed, "destroy event should fail without heavy source")

    # Deploy one heavy card then destroy should succeed.
    main_player = engine.get_player("主控玩家")
    main_player.holy_water = 10.0
    pipe.compile_line("[主控玩家.deploy=电磁炮]")
    pipe.compile_line("[queue.flush=true]")
    pipe.compile_line("[game_event.trigger=destroy_dezheng_blue_device_with_heavy]")
    assert_true(not engine.campus_map.is_node_valid("德政楼"), "德政楼 should collapse after heavy destroy")
    assert_true(
        "场景事件:德政楼蓝光装置已摧毁" in engine.global_config.dynamic_states,
        "missing dezheng device destroyed marker",
    )
    assert_true(engine.event_checker.is_triggered("emergency"), "emergency should start after 德政楼 collapse")

    # 6 time units after emergency starts, school should explode and game ends.
    pipe.compile_line("[time.advance=6]")
    assert_true(engine.event_checker.is_triggered("explosion"), "school explosion should trigger at +6")
    assert_true(engine.game_over, "game should end after school explosion if not escaped")
    assert_true(engine.game_result == "main_player_dead", "main player should die after school explosion")

    # Gate guard blockade: cannot escape before breaking defense.
    campus2 = build_default_campus_map()
    cfg2 = GlobalConfig()
    engine2 = GameEngine(campus2, cfg2)
    main2 = PlayerRole("主控玩家", campus2, cfg2, "正门")
    engine2.register_player(main2)
    engine2.set_main_player("主控玩家")
    pipe2 = CommandPipeline(engine2)
    pipe2.compile_line("[global.main_player=主控玩家]")
    pipe2.compile_line("[scene_event.trigger=gate_guard_blockade_observation]")
    assert_true(
        "场景事件:正门保安阻拦已触发" in engine2.global_config.dynamic_states,
        "missing gate guard seen marker",
    )
    blocked = False
    try:
        pipe2.compile_line("[主控玩家.escape=正门]")
    except ValueError:
        blocked = True
    assert_true(blocked, "escape via 正门 should be blocked before guard defense is broken")

    pipe2.compile_line("[global.main_game_state=installed]")
    engine2.get_player("主控玩家").holy_water = 10.0
    pipe2.compile_line("[主控玩家.deploy=电磁炮]")
    pipe2.compile_line("[queue.flush=true]")
    pipe2.compile_line("[game_event.trigger=break_gate_guard_blockade_with_units]")
    assert_true(
        "场景事件:正门保安防线已突破" in engine2.global_config.dynamic_states,
        "missing gate guard broken marker",
    )
    pipe2.compile_line("[主控玩家.escape=正门]")
    assert_true(
        any("已通过正门逃离校园" in s for s in engine2.get_role("主控玩家").list_dynamic_states()),
        "escape should succeed after gate guard defense is broken",
    )

    # Canteen Li Qinbin event: remind -> token to main phone.
    campus3 = build_default_campus_map()
    cfg3 = GlobalConfig()
    engine3 = GameEngine(campus3, cfg3)
    main3 = PlayerRole("主控玩家", campus3, cfg3, "食堂")
    engine3.register_player(main3)
    engine3.set_main_player("主控玩家")
    pipe3 = CommandPipeline(engine3)
    pipe3.compile_line("[global.main_player=主控玩家]")
    pipe3.compile_line("[global.main_game_state=installed]")
    pipe3.compile_line("[scene_event.trigger=canteen_liqinbin_prompt]")
    assert_true(
        "场景事件:食堂李秦彬提醒待抉择" in engine3.global_config.dynamic_states,
        "missing canteen pending marker",
    )
    t3 = float(engine3.global_config.current_time_unit)
    pipe3.compile_line("[game_event.trigger=canteen_liqinbin_remind_and_token]")
    assert_true(abs(engine3.global_config.current_time_unit - (t3 + 1.5)) < 1e-9, "canteen remind should advance 1.5")
    assert_true(
        "场景事件:食堂李秦彬提醒已完成" in engine3.global_config.dynamic_states,
        "missing canteen done marker",
    )
    assert_true(
        "主控手机效果:皇室令牌已激活" in engine3.global_config.dynamic_states,
        "missing token marker",
    )
    assert_true(main3.card_valid == 8, "token should set main card_valid to 8")

    print("PASS: scene event command test")


if __name__ == "__main__":
    main()
