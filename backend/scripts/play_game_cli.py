# -*- coding: utf-8 -*-
"""
Module purpose:
- Provide an interactive CLI game loop so the user can directly play the game with LLM-driven turns.

Functions:
- build_runtime(): create one playable runtime world with main player and core角色初始位置.
- play_loop(api_key, model): run turn-based input loop, stream narrative each turn, apply commands, and stop on game-over.
- main(): parse CLI args and start the interactive session.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend import CommandPipeline, GameEngine, GlobalConfig, PlayerRole, Role, build_default_campus_map
from backend.gemini_client import GeminiClient
from backend.llm_agent_bridge import LLMAgentBridge

OPENING_HOTSPOT_BRANCH = "开场分支:借马超鹏热点更新"
OPENING_FLOW_BRANCH = "开场分支:流量更新"


def _parse_numbered_options(system_text: str) -> dict[int, str]:
    """Parse numbered options from previous system narrative text."""

    rows: dict[int, str] = {}
    for line in system_text.splitlines():
        match = re.match(r"^\s*(\d+)\s*[\.．、]\s*(.+?)\s*$", line.strip())
        if not match:
            continue
        rows[int(match.group(1))] = match.group(2).strip()
    return rows


def _resolve_user_action_text(user_input: str, last_system_text: str) -> str:
    """Resolve a numeric user input (e.g. 1/2/3) to previous option text."""

    raw = user_input.strip()
    if not raw.isdigit():
        return raw
    options = _parse_numbered_options(last_system_text)
    selected = options.get(int(raw))
    return selected if selected else raw


def _extract_auto_move_target(action_text: str, neighbors: list[str]) -> str | None:
    """Extract one adjacent destination from action text if it is a clear move intent."""

    text = action_text.strip()
    if not text:
        return None
    for blocked in ("离开", "逃离", "逃出", "翻墙", "离校"):
        if blocked in text:
            return None
    for blocked in ("不去", "别去", "不要去"):
        if blocked in text:
            return None

    ordered_neighbors = sorted(neighbors, key=len, reverse=True)
    for node_name in ordered_neighbors:
        if text == node_name:
            return node_name
        patterns = (
            f"去{node_name}",
            f"到{node_name}",
            f"前往{node_name}",
            f"走向{node_name}",
            f"跑向{node_name}",
            f"赶往{node_name}",
            f"移动到{node_name}",
        )
        if any(p in text for p in patterns):
            return node_name
    return None


def _try_auto_apply_main_move(
    engine: GameEngine,
    pipeline: CommandPipeline,
    action_text: str,
) -> dict[str, Any] | None:
    """
    Backend-smart movement:
    - If action implies move to adjacent node, apply move + queue.flush + time.advance automatically.
    """

    main_name = engine.main_player_name
    if not main_name:
        return None
    role = engine.get_role(main_name)
    current_node = engine.campus_map.get_node(role.current_location)
    neighbors = sorted(
        [
            name
            for name in current_node.neighbors
            if engine.campus_map.get_node(name).valid
        ]
    )
    target = _extract_auto_move_target(action_text, neighbors)
    if not target:
        return None

    from_node = role.current_location
    move_cost = float(engine.global_config.get_effective_main_move_cost(1.0))
    pipeline.compile_line(f"[{main_name}.move={target}]")
    pipeline.compile_line("[queue.flush=true]")
    pipeline.compile_line(f"[time.advance={move_cost:g}]")
    return {
        "from_node": from_node,
        "to_node": target,
        "time_advanced": move_cost,
    }


def _apply_opening_choice_markers(
    engine: GameEngine,
    pipeline: CommandPipeline,
    action_text: str,
) -> None:
    """
    Persist opening branch markers from direct user choices so downstream logic is deterministic.
    """

    text = action_text.strip()
    if not text:
        return

    states = set(engine.global_config.dynamic_states)
    hotspot_keys = ("借马超鹏热点更新", "借热点更新", "借马超鹏热点", "蹭马超鹏热点")
    flow_keys = ("流量更新", "用流量更新")

    if any(key in text for key in hotspot_keys):
        if OPENING_HOTSPOT_BRANCH not in states:
            pipeline.compile_line(f"[global.state+={OPENING_HOTSPOT_BRANCH}]")
        # Hotspot route implies the main player's own phone/client is not usable for now.
        pipeline.compile_line("[global.main_game_state=confiscated]")
        return

    if any(key in text for key in flow_keys):
        if OPENING_FLOW_BRANCH not in states:
            pipeline.compile_line(f"[global.state+={OPENING_FLOW_BRANCH}]")
        return


def build_runtime() -> tuple[GameEngine, CommandPipeline]:
    """Create one runtime world for interactive play."""

    campus = build_default_campus_map()
    cfg = GlobalConfig()
    engine = GameEngine(campus, cfg)

    main_player = PlayerRole("主控玩家", campus, cfg, "东教学楼内部")
    engine.register_player(main_player)
    engine.set_main_player("主控玩家")

    # Core non-player roles.
    Role("李再斌", campus, cfg, "宿舍")
    Role("黎诺存", campus, cfg, "西教学楼南")
    Role("颜宏帆", campus, cfg, "东教学楼内部")

    # Enemy runtime uses PlayerRole mechanics (holy water/deploy/card deck).
    for name, profile in engine.character_profiles.items():
        if "敌对" not in str(profile.alignment):
            continue
        if name not in campus.roles:
            continue
        engine.promote_role_to_player(name, card_deck=list(profile.card_deck), card_valid=4)

    pipeline = CommandPipeline(engine)
    pipeline.compile_line("[global.main_player=主控玩家]")
    return engine, pipeline


def play_loop(api_key: str, model: str) -> None:
    """Run interactive game loop until quit or game-over."""

    engine, pipeline = build_runtime()
    client = GeminiClient(api_key=api_key, model=model)
    bridge = LLMAgentBridge(client)
    recent_turns = [
        "User: 开始游戏",
        "System: 你是向西中学的一名普通学生。最近，一款名为《皇室战争》的游戏在班级里掀起了狂热的风暴，即便是最严厉的课堂，也有人甘冒被抓的风险在课桌下偷偷沉迷于此，也包括你和你的好朋友罗宾，陈洛和马超鹏。\n枯燥的数学课上，老师正在讲解着复数的定义。这正如催眠曲般回荡。你埋下头偷偷按亮手机，一条爆炸性的消息突然跃入眼帘，好消息：《皇室战争：超现实大更新》！\n\"超现实？\"你盯着屏幕微微发愣，\"这是什么意思？以前怎么从来没听说过这个版本？\"\n尽管心中充满疑惑，但对新版本的好奇心犹如猫挠。你激动得掌心微汗，必须立刻决断，请选择：\n1. 流量更新\n2. 借马超鹏热点更新\n3. 不更新，先认真听数学课",
    ]

    print("游戏开始。输入自然语言行动；输入 `quit` 退出。")
    print("\n[开场]")
    print(recent_turns[1].replace("System: ", "", 1))
    last_system_text = recent_turns[1].replace("System: ", "", 1)
    while True:
        main = engine.get_player(engine.main_player_name or "主控玩家")
        role = engine.get_role(engine.main_player_name or "主控玩家")
        print(
            f"\n[状态] t={engine.global_config.current_time_unit:g} "
            f"地点={role.current_location} HP={role.health:g} 圣水={main.holy_water:g}"
        )
        user_input = input("你> ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("已退出。")
            return

        resolved_action_text = _resolve_user_action_text(user_input, last_system_text)
        backend_step_notes: list[str] = []
        _apply_opening_choice_markers(engine, pipeline, resolved_action_text)
        allow_narrative_time_advance = True
        block_main_player_move = False
        auto_move = _try_auto_apply_main_move(engine, pipeline, resolved_action_text)
        if auto_move is not None:
            allow_narrative_time_advance = False
            block_main_player_move = True
            backend_step_notes.append(
                "主控玩家已由后台自动执行相邻移动："
                f"{auto_move['from_node']} -> {auto_move['to_node']}，"
                f"并已自动推进 time.advance={float(auto_move['time_advanced']):g}。"
            )
            print(
                f"[系统] 自动移动解析：{auto_move['from_node']} -> {auto_move['to_node']} "
                f"(time+={float(auto_move['time_advanced']):g})"
            )

        final_packet = None
        print("\n[剧情]")
        for event in bridge.run_step_stream(
            pipeline=pipeline,
            recent_user_turns=recent_turns,
            current_user_input=resolved_action_text,
            apply_commands=True,
            backend_step_notes=backend_step_notes,
            allow_narrative_time_advance=allow_narrative_time_advance,
            block_main_player_move=block_main_player_move,
        ):
            if event["type"] == "narrative_chunk":
                print(event["text"], end="", flush=True)
            elif event["type"] == "final":
                final_packet = event
        print()

        if final_packet is not None and final_packet["errors"]:
            print("[系统] 命令执行异常：")
            for err in final_packet["errors"]:
                print(f"- {err}")

        if final_packet is not None:
            system_text = str(final_packet.get("main_text", "")).strip()
            recent_turns = [*recent_turns[-4:], f"User: {resolved_action_text}", f"System: {system_text}"]
            last_system_text = system_text

        if engine.game_over:
            print(f"\n[结束] 游戏结束，结果={engine.game_result}")
            return


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive CLI play loop for campus game.")
    parser.add_argument("--api-key", default="", help="Gemini API key. Empty means use GOOGLE_API_KEY env var.")
    parser.add_argument("--model", default="gemini-3-flash-preview", help="Gemini model name.")
    args = parser.parse_args()

    api_key = (args.api_key or os.getenv("GOOGLE_API_KEY", "")).strip()
    if not api_key:
        raise RuntimeError("Missing Gemini API key. Provide --api-key or set GOOGLE_API_KEY.")
    play_loop(api_key=api_key, model=args.model)


if __name__ == "__main__":
    main()
