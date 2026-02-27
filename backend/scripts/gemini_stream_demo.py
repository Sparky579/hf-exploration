"""
Module purpose:
- Demonstrate one LLM-driven game step with Gemini stream output.

Script flow:
1. Build a minimal runtime world.
2. Build command pipeline and seed one enemy trigger.
3. Send requests through LLMAgentBridge:
   - main narrative in stream mode,
   - hidden enemy trigger processing only when enemy trigger fires.
4. Print streamed narrative and parsed command summary.
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


def build_demo_runtime() -> tuple[GameEngine, CommandPipeline]:
    """Build a minimal world with one main player and enemy roles."""

    campus = build_default_campus_map()
    cfg = GlobalConfig()
    engine = GameEngine(campus, cfg)

    main_player = PlayerRole("主控玩家", campus, cfg, "东教学楼内部")
    engine.register_player(main_player)
    engine.set_main_player("主控玩家")

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
    pipeline.compile_line("global.main_player=主控玩家")
    pipeline.compile_line("trigger.add=角色:颜宏帆|时间0.5 若颜宏帆在教室 则 颜宏帆下出小骷髅")
    return engine, pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Gemini stream demo for campus game.")
    parser.add_argument("--api-key", default="", help="Gemini API key. Empty means use GOOGLE_API_KEY env var.")
    parser.add_argument("--model", default="gemini-3-flash-preview", help="Gemini model name.")
    parser.add_argument("--input", default="我先观察教室里的情况，然后决定要不要更新游戏。", help="Current user input.")
    parser.add_argument("--apply-commands", action="store_true", help="Apply model commands to runtime.")
    args = parser.parse_args()

    api_key = (args.api_key or os.getenv("GOOGLE_API_KEY", "")).strip()
    if not api_key:
        raise RuntimeError("Missing Gemini API key. Provide --api-key or set GOOGLE_API_KEY.")

    _, pipeline = build_demo_runtime()
    client = GeminiClient(api_key=api_key, model=args.model)
    bridge = LLMAgentBridge(client)

    recent_turns = [
        "User: 我现在在东教学楼内部，先别乱动。",
        "System: 你看到课堂正常进行，手机弹出超现实超级更新提示。",
    ]

    final_packet = None
    print("==== Narrative Stream Start ====")
    for event in bridge.run_step_stream(
        pipeline=pipeline,
        recent_user_turns=recent_turns,
        current_user_input=args.input,
        apply_commands=args.apply_commands,
    ):
        if event["type"] == "narrative_chunk":
            print(event["text"], end="", flush=True)
        elif event["type"] == "final":
            final_packet = event
    print("\n==== Narrative Stream End ====")

    if final_packet is None:
        raise RuntimeError("No final packet returned.")

    print("\n==== Parsed Commands ====")
    print("Narrative:")
    for line in final_packet["narrative_commands"]:
        print(f"- {line}")
    print("Enemy:")
    for line in final_packet["enemy_commands"]:
        print(f"- {line}")

    print("\n==== Apply Result ====")
    print(f"Applied: {len(final_packet['applied_commands'])}")
    for line in final_packet["applied_commands"]:
        print(f"- {line}")
    if final_packet["errors"]:
        print("Errors:")
        for line in final_packet["errors"]:
            print(f"- {line}")


if __name__ == "__main__":
    main()
