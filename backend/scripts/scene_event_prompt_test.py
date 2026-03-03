"""
Module purpose:
- Verify scene-event prompting context generation.

Checks:
1. At t<=5 and in 东教学楼内部 -> scene event candidate should be present.
2. Candidate includes `scene_event.trigger=<id>` command hint for model-side decision.
3. At t>5 -> scene event candidate should not be present.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend import CommandPipeline, GameEngine, GlobalConfig, PlayerRole, Role, build_default_campus_map
from backend.state_snapshot import build_step_context


def assert_true(cond: bool, message: str) -> None:
    if not cond:
        raise AssertionError(message)


def build_runtime() -> tuple[GameEngine, CommandPipeline]:
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
    return engine, pipe


def build_dezheng_runtime() -> tuple[GameEngine, CommandPipeline]:
    campus = build_default_campus_map()
    cfg = GlobalConfig()
    engine = GameEngine(campus, cfg)
    main = PlayerRole("主控玩家", campus, cfg, "德政楼")
    engine.register_player(main)
    engine.set_main_player("主控玩家")
    pipe = CommandPipeline(engine)
    pipe.compile_line("[global.main_player=主控玩家]")
    return engine, pipe


def build_international_runtime() -> tuple[GameEngine, CommandPipeline]:
    campus = build_default_campus_map()
    cfg = GlobalConfig()
    engine = GameEngine(campus, cfg)
    main = PlayerRole("主控玩家", campus, cfg, "国际部")
    engine.register_player(main)
    engine.set_main_player("主控玩家")
    Role("信息老师", campus, cfg, "国际部")
    pipe = CommandPipeline(engine)
    pipe.compile_line("[global.main_player=主控玩家]")
    return engine, pipe


def build_gate_runtime() -> tuple[GameEngine, CommandPipeline]:
    campus = build_default_campus_map()
    cfg = GlobalConfig()
    engine = GameEngine(campus, cfg)
    main = PlayerRole("主控玩家", campus, cfg, "正门")
    engine.register_player(main)
    engine.set_main_player("主控玩家")
    pipe = CommandPipeline(engine)
    pipe.compile_line("[global.main_player=主控玩家]")
    return engine, pipe


def build_canteen_runtime() -> tuple[GameEngine, CommandPipeline]:
    campus = build_default_campus_map()
    cfg = GlobalConfig()
    engine = GameEngine(campus, cfg)
    main = PlayerRole("主控玩家", campus, cfg, "食堂")
    engine.register_player(main)
    engine.set_main_player("主控玩家")
    pipe = CommandPipeline(engine)
    pipe.compile_line("[global.main_player=主控玩家]")
    return engine, pipe


def main() -> None:
    # Case 1: candidate exists.
    e1, p1 = build_runtime()
    c1 = build_step_context(
        engine=e1,
        pipeline=p1,
        recent_user_turns=["User: 开始", "System: 开场"],
        current_user_input="去东教学楼南",
    )
    events1 = c1.get("scene_events", [])
    assert_true(bool(events1), "scene_events candidate should exist at t<=5")
    assert_true(
        str(events1[0].get("id", "")) == "east_toilet_yanhongfan_encounter",
        "unexpected scene event id",
    )
    assert_true(
        str(events1[0].get("trigger_command", "")) == "[scene_event.trigger=east_toilet_yanhongfan_encounter]",
        "missing scene event trigger command hint",
    )

    # Case 2: international teacher encounter candidate exists in normal time.
    e2, p2 = build_international_runtime()
    c2 = build_step_context(
        engine=e2,
        pipeline=p2,
        recent_user_turns=["User: 去国际部", "System: 你来到国际部"],
        current_user_input="停下看看那道熟悉的身影",
    )
    events2 = c2.get("scene_events", [])
    intl_ids = {str(item.get("id", "")) for item in events2}
    assert_true(
        "international_it_teacher_encounter" in intl_ids,
        "international teacher event should exist before alert and before collapse",
    )
    p2.compile_line("[scene_event.trigger=international_it_teacher_encounter]")
    c2b = build_step_context(
        engine=e2,
        pipeline=p2,
        recent_user_turns=["User: 靠近人影", "System: 你看见模糊身影"],
        current_user_input="继续靠近看清",
    )
    pre_ids = [str(item.get("id", "")) for item in c2b.get("predefined_events", [])]
    assert_true(
        pre_ids == ["international_it_teacher_reveal_confiscate"],
        "teacher pending state should expose only reveal_confiscate event",
    )

    # Case 3: time window passed.
    e3, p3 = build_runtime()
    p3.compile_line("[time.advance=5]")
    c3 = build_step_context(
        engine=e3,
        pipeline=p3,
        recent_user_turns=["User: 开始", "System: 开场"],
        current_user_input="我原地搜查一下",
    )
    assert_true(not c3.get("scene_events", []), "scene event should not trigger when t>5")

    # Case 4: 陈洛 event appears before t<10 in 南教学楼.
    e4, p4 = build_runtime()
    p4.compile_line("[主控玩家.location=南教学楼]")
    c4 = build_step_context(
        engine=e4,
        pipeline=p4,
        recent_user_turns=["User: 去南教学楼", "System: 你到达南教学楼"],
        current_user_input="靠近那个同学",
    )
    ids4 = {str(item.get("id", "")) for item in c4.get("scene_events", [])}
    assert_true(
        "south_building_chenluo_heal_encounter" in ids4,
        "chenluo event should exist at 南教学楼 when t<10",
    )

    # Case 5: 陈洛 event disappears after t>=10.
    e5, p5 = build_runtime()
    p5.compile_line("[主控玩家.location=南教学楼]")
    p5.compile_line("[time.advance=10]")
    c5 = build_step_context(
        engine=e5,
        pipeline=p5,
        recent_user_turns=["User: 继续前进", "System: 时间流逝"],
        current_user_input="查看南教学楼",
    )
    ids5 = {str(item.get("id", "")) for item in c5.get("scene_events", [])}
    assert_true(
        "south_building_chenluo_heal_encounter" not in ids5,
        "chenluo event should not exist when t>=10",
    )

    # Case 6: 德政楼蓝光装置 scene event exists.
    e6, p6 = build_dezheng_runtime()
    c6 = build_step_context(
        engine=e6,
        pipeline=p6,
        recent_user_turns=["User: 去德政楼", "System: 你到了德政楼"],
        current_user_input="查看蓝光源头",
    )
    ids6 = {str(item.get("id", "")) for item in c6.get("scene_events", [])}
    assert_true(
        "dezheng_blue_device_observation" in ids6,
        "dezheng blue device scene event should exist when at 德政楼 and node valid",
    )

    # Case 7: after observation, predefined heavy-destroy event appears.
    p6.compile_line("[scene_event.trigger=dezheng_blue_device_observation]")
    c7 = build_step_context(
        engine=e6,
        pipeline=p6,
        recent_user_turns=["User: 查看装置", "System: 你看见蓝光装置"],
        current_user_input="尝试攻击装置",
    )
    pre_ids7 = {str(item.get("id", "")) for item in c7.get("predefined_events", [])}
    assert_true(
        "destroy_dezheng_blue_device_with_heavy" in pre_ids7,
        "dezheng heavy destroy predefined event should appear after observation",
    )

    # Case 8: gate guard observation scene event exists at 正门.
    e8, p8 = build_gate_runtime()
    c8 = build_step_context(
        engine=e8,
        pipeline=p8,
        recent_user_turns=["User: 去正门", "System: 你到了正门"],
        current_user_input="看看门口",
    )
    ids8 = {str(item.get("id", "")) for item in c8.get("scene_events", [])}
    assert_true(
        "gate_guard_blockade_observation" in ids8,
        "gate guard scene event should exist at 正门 when blockade not broken",
    )
    p8.compile_line("[scene_event.trigger=gate_guard_blockade_observation]")
    c8b = build_step_context(
        engine=e8,
        pipeline=p8,
        recent_user_turns=["User: 观察门口", "System: 保安挡在门前"],
        current_user_input="先观察",
    )
    pre_ids8b = {str(item.get("id", "")) for item in c8b.get("predefined_events", [])}
    assert_true(
        "break_gate_guard_blockade_with_units" not in pre_ids8b,
        "gate break predefined event should not be exposed without explicit attack intent",
    )

    # Case 9: once user intent is explicit and troop power is enough, gate-break predefined event appears.
    p8.compile_line("[global.main_game_state=installed]")
    e8.get_player("主控玩家").holy_water = 10.0
    p8.compile_line("[主控玩家.deploy=电磁炮]")
    p8.compile_line("[queue.flush=true]")
    c9 = build_step_context(
        engine=e8,
        pipeline=p8,
        recent_user_turns=["User: 我要冲出去", "System: 保安还在拦你"],
        current_user_input="命令部队攻击保安突破",
    )
    pre_ids9 = {str(item.get("id", "")) for item in c9.get("predefined_events", [])}
    assert_true(
        "break_gate_guard_blockade_with_units" in pre_ids9,
        "gate break predefined event should appear with explicit break intent and enough power",
    )

    # Case 10: canteen event asks for reminder and exposes token event on explicit remind intent.
    e10, p10 = build_canteen_runtime()
    c10 = build_step_context(
        engine=e10,
        pipeline=p10,
        recent_user_turns=["User: 去食堂", "System: 你来到食堂"],
        current_user_input="看看食堂里那个低头吃饭的同学",
    )
    ids10 = {str(item.get("id", "")) for item in c10.get("scene_events", [])}
    assert_true(
        "canteen_liqinbin_prompt" in ids10,
        "canteen liqinbin prompt event should exist at 食堂",
    )
    p10.compile_line("[scene_event.trigger=canteen_liqinbin_prompt]")
    c10b = build_step_context(
        engine=e10,
        pipeline=p10,
        recent_user_turns=["User: 提醒他", "System: 你准备提醒他"],
        current_user_input="提醒李秦彬校园出事了",
    )
    pre_ids10b = {str(item.get("id", "")) for item in c10b.get("predefined_events", [])}
    assert_true(
        "canteen_liqinbin_remind_and_token" in pre_ids10b,
        "canteen token predefined event should appear on remind intent",
    )

    print("PASS: scene event prompt test")


if __name__ == "__main__":
    main()
