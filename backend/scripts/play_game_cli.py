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
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend import CommandPipeline, GameEngine, GlobalConfig, PlayerRole, Role, build_default_campus_map
from backend.gemini_client import GeminiClient
from backend.llm_agent_bridge import LLMAgentBridge


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
        "System: 你是向西中学的一名普通学生。最近，一款名为《皇室战争》的游戏在班级里掀起了狂热的风暴，即便是最严厉的课堂，也有人甘冒被抓的风险在课桌下偷偷沉迷于此，也包括你和你的好朋友罗宾，陈洛和马超鹏。\n枯燥的数学课上，老师正在讲解着复数的定义。这正如催眠曲般回荡。你埋下头偷偷按亮手机，一条爆炸性的消息突然跃入眼帘——好消息：《皇室战争：超现实大更新》！\n“超现实？”你盯着屏幕微微发愣，“这是什么意思？以前怎么从来没听说过这个版本？”\n尽管心中充满疑惑，但对新版本的好奇心犹如猫挠。你激动得掌心微汗，必须立刻决断，请选择：\n1. 流量更新\n2. 借马超鹏热点更新\n3. 不更新",
    ]

    print("游戏开始。输入自然语言行动；输入 `quit` 退出。")
    print("\n[开场]")
    print(recent_turns[1].replace("System: ", "", 1))
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

        final_packet = None
        print("\n[剧情]")
        for event in bridge.run_step_stream(
            pipeline=pipeline,
            recent_user_turns=recent_turns,
            current_user_input=user_input,
            apply_commands=True,
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
            if len(system_text) > 220:
                system_text = system_text[:220] + "..."
            recent_turns = [*recent_turns[-2:], f"User: {user_input}", f"System: {system_text}"]

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
