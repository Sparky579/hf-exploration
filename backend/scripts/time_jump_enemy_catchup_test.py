"""
Module purpose:
- Verify enemy trigger catch-up when narrative advances time by 2 in one round.

Functions:
- assert_true(cond, message): minimal assertion helper.
- build_runtime(): create engine/pipeline runtime with main player and core enemy roles.
- main(): run one LLMAgentBridge step with fake LLM responses and confirm that:
  1) time jump triggers enemy trigger firing,
  2) post-narrative enemy catch-up processes and marks that trigger handled in the same round.
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
    """Deterministic fake client for bridge testing."""

    def stream_generate_text(self, prompt: str):
        text = (
            "[command]\n"
            "[global.main_player=主控玩家]\n"
            "[global.battle=none]\n"
            "[global.emergency=false]\n"
            "[time.advance=2]\n"
            "[/command]\n"
            "剧情继续。"
        )
        yield text

    def generate_text(self, prompt: str) -> str:
        # Initial enemy trigger planning prompt can be empty; fallback seeding exists.
        if "敌对角色触发器初始化代理" in prompt:
            return "[command]\n[/command]"
        # Enemy trigger handling prompt: write one harmless command.
        return "[command]\n[character.李再斌.history+=time_jump_catchup]\n[/command]"


def assert_true(cond: bool, message: str) -> None:
    if not cond:
        raise AssertionError(message)


def build_runtime() -> tuple[GameEngine, CommandPipeline]:
    campus = build_default_campus_map()
    cfg = GlobalConfig()
    engine = GameEngine(campus, cfg)

    main_player = PlayerRole("主控玩家", campus, cfg, "东教学楼内部")
    engine.register_player(main_player)
    engine.set_main_player("主控玩家")

    Role("李再斌", campus, cfg, "宿舍")
    Role("黎诺存", campus, cfg, "西教学楼南")
    Role("颜宏帆", campus, cfg, "东教学楼内部")

    for name, profile in engine.character_profiles.items():
        if "敌对" not in str(profile.alignment):
            continue
        if name not in campus.roles:
            continue
        engine.promote_role_to_player(name, card_deck=list(profile.card_deck), card_valid=4)

    pipeline = CommandPipeline(engine)
    pipeline.compile_line("[global.main_player=主控玩家]")
    return engine, pipeline


def main() -> None:
    engine, pipeline = build_runtime()
    # Trigger should fire only after time jump > 1.5.
    item = engine.global_config.add_scripted_trigger(
        "角色:李再斌|时间1.5 若李再斌 alive and not left then 李再斌 idle"
    )
    trigger_id = int(item["id"])

    bridge = LLMAgentBridge(FakeClient())
    final_packet = None
    for event in bridge.run_step_stream(
        pipeline=pipeline,
        recent_user_turns=["User: 开始", "System: 开场剧情"],
        current_user_input="我先处理一件很耗时的事",
        apply_commands=True,
    ):
        if event["type"] == "final":
            final_packet = event

    assert_true(final_packet is not None, "bridge should return final packet")
    trigger = engine.global_config.get_scripted_trigger(trigger_id)
    assert_true(bool(trigger["triggered"]), "trigger should be fired after time.advance=2")
    assert_true(bool(trigger["handled"]), "trigger should be handled by enemy catch-up in same round")
    print("PASS: time jump enemy catch-up test")


if __name__ == "__main__":
    main()

