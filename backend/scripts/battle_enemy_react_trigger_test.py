"""
Module purpose:
- Verify battle rounds inject enemy due trigger so hidden enemy thread can react.

Checks:
1. When global battle target is a living enemy and no due trigger exists,
   bridge should inject one immediate enemy trigger and process it.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend import CommandPipeline, GameEngine, GlobalConfig, PlayerRole, Role, build_default_campus_map
from backend.llm_agent_bridge import LLMAgentBridge


class FakeClient:
    def stream_generate_text(self, prompt: str):
        yield (
            "[command]\n"
            "[global.main_player=主控玩家]\n"
            "[global.battle=李再斌]\n"
            "[global.emergency=false]\n"
            "[/command]\n"
            "剧情"
        )

    def generate_text(self, prompt: str) -> str:
        # Enemy thread writes one harmless history line.
        if "敌对角色触发器执行代理" in prompt:
            return "[command]\n[character.李再斌.history+=battle_react_tick]\n[/command]"
        return "[command]\n[/command]"


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
    Role("李再斌", campus, cfg, "宿舍")
    profile = engine.get_character_profile("李再斌")
    engine.promote_role_to_player("李再斌", card_deck=list(profile.card_deck), card_valid=4)

    pipe = CommandPipeline(engine)
    pipe.compile_line("[global.main_player=主控玩家]")

    bridge = LLMAgentBridge(FakeClient())  # type: ignore[arg-type]
    final_packet = None
    for event in bridge.run_step_stream(
        pipeline=pipe,
        recent_user_turns=["User: 开始", "System: 开场"],
        current_user_input="进入战斗",
        apply_commands=True,
    ):
        if event["type"] == "final":
            final_packet = event

    assert_true(final_packet is not None, "bridge should return final packet")
    profile = engine.get_character_profile("李再斌")
    assert_true("battle_react_tick" in profile.history, "enemy hidden thread should react in battle round")
    print("PASS: battle enemy react trigger test")


if __name__ == "__main__":
    main()

