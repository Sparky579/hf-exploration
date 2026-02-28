"""
Module purpose:
- Build structured runtime snapshots for LLM calls.

Functions:
- build_step_context(...): package full step context (world, global, player, scene, logs, syntax).
- extract_main_player_state(engine): package main player detail block.
- extract_all_player_states(engine): package all runtime player states by name.
- extract_scene_state(engine, node_name): package current scene detail and roles.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .command_pipeline import CommandPipeline
from .constants import MOVE_TIME_COST
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
    backend_step_notes: list[str] | None = None,
) -> dict[str, Any]:
    """Build the full context payload required for one LLM step."""

    main_player = extract_main_player_state(engine)
    all_players = extract_all_player_states(engine)
    move_profile = _build_main_player_move_profile(engine)
    current_node = main_player["location"]
    scene_state = extract_scene_state(engine, current_node)
    scene_events = _build_scene_events(engine, current_user_input)
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
            "dynamic_states_recent_15": list(engine.global_config.dynamic_states[-15:]),
            "battle_state": engine.global_config.battle_state,
            "main_game_state": engine.global_config.main_game_state,
            "can_main_player_gain_holy_water": engine.global_config.can_main_player_gain_holy_water,
            "main_player": engine.main_player_name,
            "team_companions": engine.global_config.list_team_companions(),
            "main_player_move_time_cost": move_profile["effective_move_time_cost"],
            "scripted_triggers": engine.global_config.list_scripted_triggers(),
            "fired_unhandled_triggers": engine.global_config.list_fired_unhandled_triggers(),
            "trigger_window_n_to_n_plus_1_5": engine.global_config.list_triggers_until(
                end_time=float(engine.global_config.current_time_unit) + 1.5,
                include_handled=False,
            ),
            "trigger_window_n_to_n_plus_2_0": engine.global_config.list_triggers_until(
                end_time=float(engine.global_config.current_time_unit) + 2.0,
                include_handled=False,
            ),
            "recent_trigger_history": engine.event_checker.recent_trigger_history(15),
            "game_over": engine.game_over,
            "game_result": engine.game_result,
        },
        "main_player_state": main_player,
        "team_move_profile": move_profile,
        "team_companion_playable_cards": _build_team_companion_playable_cards(engine),
        "players": all_players,
        "current_scene": scene_state,
        "scene_events": scene_events,
        "character_profiles": character_profiles,
        "companions": companions,
        "recent_user_turns": list(recent_user_turns[-6:]),
        "current_user_input": current_user_input,
        "backend_step_notes": list(backend_step_notes or []),
        "console_syntax": syntax_text,
        "recent_command_logs": pipeline.get_recent_logs(15),
        "queue_length": len(pipeline.message_queue),
        "main_player_sensing_scope": sensing_scope,
        "map_adjacency": _build_map_adjacency(engine),
        "nearby_trigger_hints": _collect_nearby_trigger_hints(
            engine=engine,
            triggers=engine.global_config.list_triggers_until(
                end_time=float(engine.global_config.current_time_unit) + 1.5,
                include_handled=False,
            ),
            sensing_scope=sensing_scope,
        ),
        "nearby_trigger_hints_n_to_n_plus_2_0": _collect_nearby_trigger_hints(
            engine=engine,
            triggers=engine.global_config.list_triggers_until(
                end_time=float(engine.global_config.current_time_unit) + 2.0,
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
    move_profile = _build_main_player_move_profile(engine)
    playable_cards_detail = _build_playable_card_details(player)
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
        "playable_cards_detail": playable_cards_detail,
        "team_move_profile": move_profile,
        "recommended_move_time_advance": move_profile["effective_move_time_cost"],
        "active_units": active_units,
    }


def extract_all_player_states(engine: GameEngine) -> dict[str, dict[str, Any]]:
    """Extract all runtime player states for hidden-thread planning."""

    rows: dict[str, dict[str, Any]] = {}
    for name, player in engine.players.items():
        role = engine.get_role(name)
        rows[name] = {
            "name": name,
            "health": role.health,
            "holy_water": player.holy_water,
            "location": role.current_location,
            "moving": role.query_movement_status(),
            "battle_target": role.battle_target,
            "card_deck": list(player.card_deck),
            "card_valid": player.card_valid,
            "playable_cards": player.playable_cards(),
            "playable_cards_detail": _build_playable_card_details(player),
            "active_unit_count": len(player.active_units),
        }
    return rows


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
        "unit_presence": _extract_scene_unit_presence(engine, node_name),
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


def _build_map_adjacency(engine: GameEngine) -> dict[str, list[str]]:
    """Build a dictionary of valid connected neighbors for all valid nodes."""
    adjacency = {}
    for node_name, node in engine.campus_map.nodes.items():
        if not node.valid:
            continue
        valid_neighbors = []
        for n_name in node.neighbors:
            n = engine.campus_map.get_node(n_name)
            if n.valid:
                valid_neighbors.append(n_name)
        adjacency[node_name] = sorted(valid_neighbors)
    return adjacency


def _build_main_player_move_profile(engine: GameEngine) -> dict[str, Any]:
    """Expose team-based move time so model can use it when generating move actions."""

    team_rows: list[dict[str, Any]] = []
    for name in engine.global_config.list_team_companions():
        state = engine.global_config.get_companion_state(name)
        team_rows.append(
            {
                "name": name,
                "move_time_cost": float(state.get("move_time_cost", MOVE_TIME_COST)),
                "in_team": bool(state.get("in_team", False)),
            }
        )
    effective = float(engine.global_config.get_effective_main_move_cost(float(MOVE_TIME_COST)))
    return {
        "base_move_time_cost": float(MOVE_TIME_COST),
        "effective_move_time_cost": effective,
        "team_companion_move_costs": team_rows,
    }


def _build_playable_card_details(player: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for card_name in player.playable_cards():
        if card_name not in player.available_cards:
            continue
        card = player.available_cards[card_name]
        rows.append(
            {
                "name": card.name,
                "consume": float(card.consume),
                "attack": float(card.attack),
                "health": float(card.health),
                "attack_speed": str(card.hit_speed),
                "target_preference": str(card.attack_preference),
                "card_type": str(card.unit_class),
            }
        )
    return rows


def _build_team_companion_playable_cards(engine: GameEngine) -> list[dict[str, Any]]:
    """
    Build companion card affordance hints for narrative model.
    """

    if engine.main_player_name is None:
        return []
    main_player = engine.get_player(engine.main_player_name)
    rows: list[dict[str, Any]] = []
    for name in engine.global_config.list_team_companions():
        state = engine.global_config.get_companion_state(name)
        if not bool(state.get("can_attack", False)):
            continue
        holy = float(state.get("holy_water", 0.0))
        affordable: list[str] = []
        affordable_detail: list[dict[str, Any]] = []
        for card_name in list(state.get("deck", [])):
            if card_name not in main_player.available_cards:
                continue
            card = main_player.available_cards[card_name]
            if holy + 1e-9 < float(card.consume):
                continue
            affordable.append(card_name)
            affordable_detail.append(
                {
                    "name": card.name,
                    "consume": float(card.consume),
                    "attack": float(card.attack),
                    "health": float(card.health),
                    "attack_speed": str(card.hit_speed),
                    "target_preference": str(card.attack_preference),
                    "card_type": str(card.unit_class),
                }
            )
        rows.append(
            {
                "name": name,
                "holy_water": holy,
                "affordable_cards": affordable,
                "affordable_cards_detail": affordable_detail,
            }
        )
    return rows


def _extract_scene_unit_presence(engine: GameEngine, node_name: str) -> dict[str, Any]:
    """
    Collect active deployed units currently in this scene node, grouped by owner.
    """

    unit_rows: list[dict[str, Any]] = []
    owners: dict[str, int] = {}
    for owner_name, player in engine.players.items():
        for unit in player.list_active_units():
            if unit.node_name != node_name:
                continue
            unit_rows.append(
                {
                    "unit_id": unit.unit_id,
                    "owner": owner_name,
                    "name": unit.card.name,
                    "health": float(unit.current_health),
                    "max_health": float(unit.card.health),
                    "is_wartime": bool(unit.is_wartime),
                }
            )
            owners[owner_name] = owners.get(owner_name, 0) + 1
    return {
        "total_units": len(unit_rows),
        "owners": owners,
        "units": unit_rows,
    }


def _build_scene_events(engine: GameEngine, current_user_input: str) -> list[dict[str, Any]]:
    """
    Build high-priority scene event prompts for the narrative model.

    Current event:
    - t<=5 and main player at 东教学楼内部.
    - Model decides whether user intent is enough to trigger the encounter.
    """

    if engine.main_player_name is None:
        return []
    main_name = engine.main_player_name
    now = float(engine.global_config.current_time_unit)
    main_location = engine.get_role(main_name).current_location
    marker = "场景事件:厕所遭遇颜宏帆已触发"
    if marker in set(engine.global_config.dynamic_states):
        return []
    if engine.global_config.battle_state is not None:
        return []
    if now > 5.0:
        return []
    if main_location != "东教学楼内部":
        return []
    if not _is_role_alive(engine, "颜宏帆"):
        return []

    return [
        {
            "id": "east_toilet_yanhongfan_encounter",
            "title": "东教学楼厕所遭遇颜宏帆",
            "scene": "东教学楼内部",
            "priority": "high",
            "trigger_when": "t<=5 且主控在东教学楼内部；是否触发由模型结合本轮用户意图判断",
            "should_model_decide_trigger": True,
            "trigger_command": "[scene_event.trigger=east_toilet_yanhongfan_encounter]",
            "suggested_intent_examples": [
                "原地搜寻",
                "查看厕所",
                "在教室内寻找异常",
                "停下观察内部",
            ],
            "narrative_hint": (
                "如果模型判定用户本轮有搜查/停留探查倾向，应触发事件："
                "在厕所隔间发现躲藏的颜宏帆，他发现你后立刻与你开战。"
            ),
            "one_shot_marker": marker,
        }
    ]


def _is_role_alive(engine: GameEngine, role_name: str) -> bool:
    if role_name in engine.character_profiles:
        if engine.get_character_profile(role_name).status != "存活":
            return False
    if role_name in engine.campus_map.roles:
        return engine.get_role(role_name).health > 0
    return False
