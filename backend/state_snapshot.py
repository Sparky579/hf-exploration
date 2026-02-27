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

BUILDING_NODE_MAP: dict[str, list[str]] = {
    "东教学楼": ["东教学楼南", "东教学楼内部", "东教学楼北"],
    "西教学楼": ["西教学楼南", "西教学楼北"],
    "南教学楼": ["南教学楼"],
    "德政楼": ["德政楼"],
    "图书馆": ["图书馆"],
    "国际部": ["国际部"],
    "宿舍": ["宿舍"],
    "食堂": ["食堂"],
    "体育馆": ["体育馆"],
    "生化楼": ["生化楼"],
    "田径场": ["田径场"],
}


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
    sensing_scope = _build_sensing_scope(engine, current_node)

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
            "trigger_window_n_to_n_plus_1_5": engine.global_config.list_triggers_until(
                end_time=float(engine.global_config.current_time_unit) + 1.5,
                include_handled=False,
            ),
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
        "main_player_sensing_scope": sensing_scope,
        "nearby_trigger_hints": _collect_nearby_trigger_hints(
            engine=engine,
            triggers=engine.global_config.list_triggers_until(
                end_time=float(engine.global_config.current_time_unit) + 1.5,
                include_handled=False,
            ),
            sensing_scope=sensing_scope,
        ),
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


def _build_sensing_scope(engine: GameEngine, center_node: str) -> dict[str, Any]:
    neighbors = sorted(engine.campus_map.get_node(center_node).neighbors)
    return {
        "center_node": center_node,
        "nearby_nodes": [center_node, *neighbors],
    }


def _collect_nearby_trigger_hints(
    engine: GameEngine,
    triggers: list[dict[str, Any]],
    sensing_scope: dict[str, Any],
) -> list[dict[str, Any]]:
    nearby_nodes = set(sensing_scope["nearby_nodes"])
    rows: list[dict[str, Any]] = []
    for item in triggers:
        if _is_trigger_nearby(engine, item, nearby_nodes):
            rows.append(dict(item))
    rows.sort(key=lambda x: (float(x["trigger_time"]), int(x["id"])))
    return rows


def _is_trigger_nearby(
    engine: GameEngine,
    trigger: dict[str, Any],
    nearby_nodes: set[str],
) -> bool:
    owner = str(trigger.get("owner", ""))
    if owner in engine.campus_map.roles:
        owner_node = engine.get_role(owner).current_location
        if owner_node in nearby_nodes:
            return True

    text = f"{trigger.get('condition', '')} {trigger.get('result', '')} {trigger.get('text', '')}"
    for node_name in nearby_nodes:
        if node_name and node_name in text:
            return True
    for building, nodes in BUILDING_NODE_MAP.items():
        if building not in text:
            continue
        if any(node in nearby_nodes for node in nodes):
            return True
    return False
