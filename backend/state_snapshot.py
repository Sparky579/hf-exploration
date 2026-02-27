"""
Module purpose:
- Build structured runtime snapshots for LLM calls.

Functions:
- build_step_context(...): package full step context (world, global, player, scene, logs, syntax).
- extract_main_player_state(engine): package main player detail block.
- extract_scene_state(engine, node_name): package current scene detail and roles.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .command_pipeline import CommandPipeline
from .engine import GameEngine
from .narrative_assets import build_world_base_setting, get_scene_paragraph


def build_step_context(
    engine: GameEngine,
    pipeline: CommandPipeline,
    recent_user_turns: list[str],
    current_user_input: str,
) -> dict[str, Any]:
    """Build the full context payload required for one LLM step."""

    main_player = extract_main_player_state(engine)
    current_node = main_player["location"]
    scene_state = extract_scene_state(engine, current_node)

    syntax_path = Path(__file__).resolve().parent / "docs" / "pipeline_syntax.md"
    syntax_text = syntax_path.read_text(encoding="utf-8") if syntax_path.exists() else ""

    character_profiles = {}
    for name, profile in engine.character_profiles.items():
        character_profiles[name] = {
            "name": profile.name,
            "alignment": profile.alignment,
            "status": profile.status,
            "description": profile.description,
            "history": list(profile.history),
            "card_deck": list(profile.card_deck),
        }

    companions = {}
    for name, state in engine.global_config.companions.items():
        companions[name] = dict(state)

    payload = {
        "world_base_setting": build_world_base_setting(),
        "story_title": engine.story_setting.title,
        "story_text": engine.story_setting.story_text,
        "global_state": {
            "time": engine.global_config.current_time_unit,
            "states": list(engine.global_config.global_states),
            "dynamic_states": list(engine.global_config.dynamic_states),
            "battle_state": engine.global_config.battle_state,
            "main_player": engine.main_player_name,
            "team_companions": engine.global_config.list_team_companions(),
            "scripted_triggers": engine.global_config.list_scripted_triggers(),
            "fired_unhandled_triggers": engine.global_config.list_fired_unhandled_triggers(),
            "recent_trigger_history": engine.event_checker.recent_trigger_history(15),
            "game_over": engine.game_over,
            "game_result": engine.game_result,
        },
        "main_player_state": main_player,
        "current_scene": scene_state,
        "character_profiles": character_profiles,
        "companions": companions,
        "recent_user_turns": list(recent_user_turns[-2:]),
        "current_user_input": current_user_input,
        "console_syntax": syntax_text,
        "recent_command_logs": pipeline.get_recent_logs(15),
        "queue_length": len(pipeline.message_queue),
    }
    return payload


def extract_main_player_state(engine: GameEngine) -> dict[str, Any]:
    """Extract detail state block for current main player."""

    if engine.main_player_name is None:
        raise ValueError("main_player is not set.")
    player = engine.get_player(engine.main_player_name)
    role = engine.get_role(engine.main_player_name)
    active_units = []
    for unit in player.list_active_units():
        active_units.append(
            {
                "unit_id": unit.unit_id,
                "name": unit.card.name,
                "health": unit.current_health,
                "max_health": unit.card.health,
                "node": unit.node_name,
                "is_wartime": unit.is_wartime,
                "deployed_time": unit.deployed_time,
            }
        )
    return {
        "name": player.name,
        "health": role.health,
        "holy_water": player.holy_water,
        "location": role.current_location,
        "moving": role.query_movement_status(),
        "battle_target": role.battle_target,
        "dynamic_states": role.list_dynamic_states(),
        "nearby_units": role.list_nearby_units(),
        "card_deck": list(player.card_deck),
        "card_valid": player.card_valid,
        "playable_cards": player.playable_cards(),
        "active_units": active_units,
    }


def extract_scene_state(engine: GameEngine, node_name: str) -> dict[str, Any]:
    """Extract current scene state and scene-role details."""

    node = engine.campus_map.get_node(node_name)
    scene_roles = []
    for role_name in node.roles:
        role = engine.get_role(role_name)
        role_block: dict[str, Any] = {
            "name": role_name,
            "health": role.health,
            "battle_target": role.battle_target,
            "dynamic_states": role.list_dynamic_states(),
            "nearby_units": role.list_nearby_units(),
            "is_player": role_name in engine.players,
        }
        if role_name in engine.character_profiles:
            profile = engine.get_character_profile(role_name)
            role_block["profile"] = {
                "alignment": profile.alignment,
                "status": profile.status,
                "description": profile.description,
                "history": list(profile.history),
                "card_deck": list(profile.card_deck),
            }
        scene_roles.append(role_block)

    return {
        "name": node.name,
        "valid": node.valid,
        "states": list(node.states),
        "neighbors": sorted(node.neighbors),
        "role_names": list(node.roles),
        "scene_paragraph": get_scene_paragraph(node.name),
        "roles": scene_roles,
    }
