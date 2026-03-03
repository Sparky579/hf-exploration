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
import re
from typing import Any

from .command_pipeline import CommandPipeline
from .constants import DYNAMIC_LZB_DEZHENG_PENDING, MOVE_TIME_COST
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

INTL_TEACHER_EVENT_PENDING = "场景事件:国际部信息老师待抉择"
INTL_TEACHER_EVENT_DONE = "场景事件:国际部信息老师已结局"
INTL_TEACHER_EVENT_CONFISCATED = "场景事件:国际部信息老师卸载游戏"
INTL_TEACHER_EXIT_BLOCKED = "场景事件:国际部信息老师封锁国际部出口"
SOUTH_BUILDING_CHENLUO_DONE = "场景事件:南教学楼遭遇陈洛已触发"
DEZHENG_BLUE_DEVICE_SEEN = "场景事件:德政楼蓝光装置已发现"
DEZHENG_BLUE_DEVICE_DESTROYED = "场景事件:德政楼蓝光装置已摧毁"
CANTEEN_LIQINBIN_PENDING = "场景事件:食堂李秦彬提醒待抉择"
CANTEEN_LIQINBIN_DONE = "场景事件:食堂李秦彬提醒已完成"
MAIN_ROYALE_TOKEN_ACTIVE = "主控手机效果:皇室令牌已激活"
CANTEEN_UNIVERSAL_KEY_PENDING = "场景事件:食堂万能钥匙待抉择"
CANTEEN_UNIVERSAL_KEY_COLLECTED = "场景事件:食堂万能钥匙已取得"
STORE_GATE_SEEN = "场景事件:小卖部铁门阻挡已触发"
STORE_GATE_OPENED = "场景事件:小卖部铁门已打开"
STORE_GATE_BROKEN = "场景事件:小卖部铁门已击破"
STORE_INSIDE_MESS = "场景事件:小卖部内部一团糟"
GYM_GATE_SEEN = "场景事件:体育馆铁门阻挡已触发"
GYM_GATE_OPENED = "场景事件:体育馆铁门已打开"
MAIN_MAGIC_SNACK_BUFF_ACTIVE = "主控效果:魔法零食拳击强化"
DEZHENG_HEAVY_MIN_ATTACK = 6.0
DEZHENG_HEAVY_MIN_CONSUME = 4.0
GATE_GUARD_SEEN_FRONT = "场景事件:正门保安阻拦已触发"
GATE_GUARD_BROKEN_FRONT = "场景事件:正门保安防线已突破"
GATE_GUARD_SEEN_BACK = "场景事件:后门保安阻拦已触发"
GATE_GUARD_BROKEN_BACK = "场景事件:后门保安防线已突破"
GATE_GUARD_BREAK_MIN_POWER = 4.0
OPENING_HOTSPOT_BRANCH = "开场分支:借马超鹏热点更新"
OPENING_FLOW_BRANCH = "开场分支:流量更新"
OPENING_MAIN_PHONE_HELD = "开场事件:主控已持有马超鹏主手机"
OPENING_HANDOFF_DONE = "开场事件:马超鹏已主动交付主手机"


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
    predefined_events = _build_predefined_events(engine, current_user_input)
    predicted_next_node = _predict_next_node_from_input(
        engine=engine,
        current_node=current_node,
        current_user_input=current_user_input,
        recent_user_turns=recent_user_turns,
    )
    predicted_scene_events: list[dict[str, Any]] = []
    predicted_predefined_events: list[dict[str, Any]] = []
    predicted_scene_role_names: list[str] = []
    predicted_nearby_trigger_hints: list[dict[str, Any]] = []
    predicted_nearby_trigger_hints_n_to_n_plus_2_0: list[dict[str, Any]] = []
    if predicted_next_node and predicted_next_node != current_node:
        predicted_scene_role_names = [
            role_name
            for role_name in list(engine.campus_map.get_node(predicted_next_node).roles)
            if _is_role_active_for_context(engine, role_name)
        ]
        predicted_scene_events = _build_scene_events(
            engine,
            current_user_input=current_user_input,
            override_location=predicted_next_node,
        )
        predicted_predefined_events = _build_predefined_events(
            engine,
            current_user_input=current_user_input,
            override_location=predicted_next_node,
        )
        predicted_sensing_scope = _build_sensing_scope(engine, predicted_next_node)
        predicted_nearby_trigger_hints = _collect_nearby_trigger_hints(
            engine=engine,
            triggers=_list_triggers_with_virtual_hints(
                engine=engine,
                end_time=float(engine.global_config.current_time_unit) + 1.5,
            ),
            sensing_scope=predicted_sensing_scope,
        )
        predicted_nearby_trigger_hints_n_to_n_plus_2_0 = _collect_nearby_trigger_hints(
            engine=engine,
            triggers=_list_triggers_with_virtual_hints(
                engine=engine,
                end_time=float(engine.global_config.current_time_unit) + 2.0,
            ),
            sensing_scope=predicted_sensing_scope,
        )
    sensing_scope = _build_sensing_scope(engine, current_node)

    syntax_path = Path(__file__).resolve().parent / "docs" / "pipeline_syntax.md"
    syntax_text = syntax_path.read_text(encoding="utf-8") if syntax_path.exists() else ""

    character_profiles = {}
    for name, profile in engine.character_profiles.items():
        if str(profile.status) != "存活":
            continue
        if name in engine.campus_map.roles and engine.get_role(name).health <= 0:
            continue
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
            "enemy_director": engine.enemy_director.snapshot(),
            "game_over": engine.game_over,
            "game_result": engine.game_result,
        },
        "main_player_state": main_player,
        "team_move_profile": move_profile,
        "team_companion_playable_cards": _build_team_companion_playable_cards(engine),
        "players": all_players,
        "current_scene": scene_state,
        "scene_events": scene_events,
        "predefined_events": predefined_events,
        "predicted_next_node": predicted_next_node,
        "predicted_scene_role_names": predicted_scene_role_names,
        "predicted_scene_events": predicted_scene_events,
        "predicted_predefined_events": predicted_predefined_events,
        "predicted_nearby_trigger_hints": predicted_nearby_trigger_hints,
        "predicted_nearby_trigger_hints_n_to_n_plus_2_0": predicted_nearby_trigger_hints_n_to_n_plus_2_0,
        "character_profiles": character_profiles,
        "companions": companions,
        "recent_user_turns": list(recent_user_turns[-6:]),
        "current_user_input": current_user_input,
        "backend_step_notes": list(backend_step_notes or []),
        "console_syntax": syntax_text,
        "recent_command_logs": pipeline.get_recent_logs(15),
        "queue_length": len(pipeline.message_queue),
        "main_player_sensing_scope": sensing_scope,
        "nearby_unit_presence": _build_nearby_unit_presence(engine, sensing_scope["nearby_nodes"]),
        "map_adjacency": _build_map_adjacency(engine),
        "nearby_trigger_hints": _collect_nearby_trigger_hints(
            engine=engine,
            triggers=_list_triggers_with_virtual_hints(
                engine=engine,
                end_time=float(engine.global_config.current_time_unit) + 1.5,
            ),
            sensing_scope=sensing_scope,
        ),
        "nearby_trigger_hints_n_to_n_plus_2_0": _collect_nearby_trigger_hints(
            engine=engine,
            triggers=_list_triggers_with_virtual_hints(
                engine=engine,
                end_time=float(engine.global_config.current_time_unit) + 2.0,
            ),
            sensing_scope=sensing_scope,
        ),
        "adjacent_trigger_hints_n_to_n_plus_2_0": _collect_adjacent_trigger_hints_n2(
            engine=engine,
            triggers=_list_triggers_with_virtual_hints(
                engine=engine,
                end_time=float(engine.global_config.current_time_unit) + 2.0,
            ),
            current_node=current_node,
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
                "attack": float(unit.card.attack),
                "health": unit.current_health,
                "max_health": unit.card.health,
                "attack_speed": str(unit.card.hit_speed),
                "target_preference": str(unit.card.attack_preference),
                "card_type": str(unit.card.unit_class),
                "is_flying": bool(unit.card.is_flying),
                "move_speed": float(unit.card.move_speed),
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
        if not _is_role_active_for_context(engine, name):
            continue
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
    visible_role_names = [name for name in node.roles if _is_role_active_for_context(engine, name)]
    for role_name in visible_role_names:
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
        "role_names": visible_role_names,
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


def _build_nearby_unit_presence(engine: GameEngine, nearby_nodes: list[str]) -> list[dict[str, Any]]:
    """
    Collect all deployed units in the main player's sensing scope (current node + neighbors).
    """

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for node_name in nearby_nodes:
        scene_rows = _extract_scene_unit_presence(engine, node_name).get("units", [])
        for unit in scene_rows:
            unit_id = str(unit.get("unit_id", "")).strip()
            if not unit_id or unit_id in seen:
                continue
            seen.add(unit_id)
            row = dict(unit)
            row["node"] = node_name
            rows.append(row)
    return rows


def _trigger_sort_key(item: dict[str, Any]) -> tuple[float, int]:
    try:
        trigger_time = float(item.get("trigger_time", 0.0))
    except (TypeError, ValueError):
        trigger_time = 0.0
    try:
        trigger_id = int(item.get("id", 10**9))
    except (TypeError, ValueError):
        trigger_id = 10**9
    return trigger_time, trigger_id


def _list_triggers_with_virtual_hints(engine: GameEngine, end_time: float) -> list[dict[str, Any]]:
    rows = engine.global_config.list_triggers_until(
        end_time=float(end_time),
        include_handled=False,
    )
    rows.extend(_build_virtual_countdown_hints(engine, end_time=float(end_time)))
    rows.sort(key=_trigger_sort_key)
    return rows


def _build_virtual_countdown_hints(engine: GameEngine, end_time: float) -> list[dict[str, Any]]:
    now = float(engine.global_config.current_time_unit)
    horizon = float(end_time)
    if horizon <= now:
        return []

    rows: list[dict[str, Any]] = []

    # Enemy deterministic plan countdown previews.
    try:
        rows.extend(engine.enemy_director.preview_planned_events_until(horizon))
    except Exception:
        pass

    # System-level countdown previews (not all are scripted trigger rows).
    alert_time = float(engine.story_setting.alert_trigger_time)
    if (not engine.event_checker.state.alert_triggered) and now <= alert_time <= horizon:
        rows.append(
            {
                "id": 890001,
                "owner": "global",
                "trigger_time": alert_time,
                "condition": "时间到达警报阈值",
                "result": "警报状态触发",
                "text": f"时间{alert_time:g} 若达到警报阈值 则 警报状态触发",
                "triggered": False,
                "handled": False,
            }
        )

    explosion_time = engine.event_checker.state.explosion_time
    if (
        explosion_time is not None
        and (not engine.event_checker.state.explosion_triggered)
        and now <= float(explosion_time) <= horizon
    ):
        rows.append(
            {
                "id": 890002,
                "owner": "global",
                "trigger_time": float(explosion_time),
                "condition": "紧急状态倒计时结束",
                "result": "学校爆炸",
                "text": f"时间{float(explosion_time):g} 若紧急倒计时结束 则 学校爆炸",
                "triggered": False,
                "handled": False,
            }
        )
    return rows


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
    rows.sort(key=_trigger_sort_key)
    return rows


def _collect_adjacent_trigger_hints_n2(
    engine: GameEngine,
    triggers: list[dict[str, Any]],
    current_node: str,
) -> list[dict[str, Any]]:
    adjacent_nodes = set(engine.campus_map.get_node(current_node).neighbors)
    rows: list[dict[str, Any]] = []
    for item in triggers:
        if _is_trigger_adjacent_to_main(engine, item, current_node, adjacent_nodes):
            rows.append(dict(item))
    rows.sort(key=_trigger_sort_key)
    return rows


def _is_trigger_adjacent_to_main(
    engine: GameEngine,
    trigger: dict[str, Any],
    current_node: str,
    adjacent_nodes: set[str],
) -> bool:
    owner = str(trigger.get("owner", "")).strip()
    if owner and owner in engine.campus_map.roles:
        try:
            owner_node = engine.get_role(owner).current_location
        except Exception:
            owner_node = ""
        if owner_node in adjacent_nodes:
            return True
        return False

    text = f"{trigger.get('condition', '')} {trigger.get('result', '')} {trigger.get('text', '')}"
    mentioned_nodes = [name for name in engine.campus_map.nodes if name and name in text]
    if mentioned_nodes:
        return any(name in adjacent_nodes for name in mentioned_nodes)
    for node_name in adjacent_nodes:
        if node_name and node_name in text:
            return True
    for building, nodes in BUILDING_NODE_MAP.items():
        if building not in text:
            continue
        # Strict adjacent-only building hint:
        # if current node itself belongs to this building cluster, skip ambiguous same-building hints.
        if current_node in set(nodes):
            continue
        if any(node in adjacent_nodes for node in nodes):
            return True
    return False


def _is_trigger_nearby(
    engine: GameEngine,
    trigger: dict[str, Any],
    nearby_nodes: set[str],
) -> bool:
    if _is_urgent_global_collapse_hint(trigger, engine.global_config.current_time_unit):
        return True
    owner = str(trigger.get("owner", ""))
    if owner == "global":
        # Global triggers in the current planning window are always relevant to narration,
        # even when condition text does not explicitly mention a node name
        # (e.g. opening branch triggers like "选择借马超鹏热点更新").
        return True
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


def _is_urgent_global_collapse_hint(trigger: dict[str, Any], now: float) -> bool:
    """
    Hard rule:
    - If collapse trigger for 东教学楼/西教学楼/德政楼 is within <=2 time units,
      always expose it to model even if out of sensing scope.
    """
    try:
        trigger_time = float(trigger.get("trigger_time", 0.0))
    except (TypeError, ValueError):
        return False
    if trigger_time < float(now) or (trigger_time - float(now)) > 2.0:
        return False
    text = f"{trigger.get('condition', '')} {trigger.get('result', '')} {trigger.get('text', '')}"
    if "建筑倒塌:" in text and any(name in text for name in ("东教学楼", "西教学楼", "德政楼")):
        return True
    if "学校爆炸" in text:
        return True
    if "火箭" in text and "东教学楼" in text:
        return True
    if "警报状态触发" in text:
        return True
    return False


def _build_map_adjacency(engine: GameEngine) -> dict[str, list[str]]:
    """Build a dictionary of connected neighbors for all nodes (including ruins)."""
    adjacency = {}
    for node_name, node in engine.campus_map.nodes.items():
        adjacency[node_name] = sorted(node.neighbors)
    return adjacency


def _predict_next_node_from_input(
    engine: GameEngine,
    current_node: str,
    current_user_input: str,
    recent_user_turns: list[str],
) -> str | None:
    """
    Heuristic parser for likely next move target.
    This is hint-only and never executes game logic.
    """

    text = str(current_user_input or "").strip()
    if not text:
        return None
    neighbors = set(engine.campus_map.get_node(current_node).neighbors)
    if not neighbors:
        return None
    option_target = _predict_next_node_from_numbered_option(
        engine=engine,
        current_node=current_node,
        current_user_input=text,
        recent_user_turns=recent_user_turns,
    )
    if option_target:
        return option_target
    for name in sorted(neighbors, key=len, reverse=True):
        if name and name in text:
            return name
    for name in sorted(engine.campus_map.nodes.keys(), key=len, reverse=True):
        if name in neighbors and name in text:
            return name
    return None


def _predict_next_node_from_numbered_option(
    engine: GameEngine,
    current_node: str,
    current_user_input: str,
    recent_user_turns: list[str],
) -> str | None:
    """
    Parse numeric choice (e.g. "1") against the latest System options block.
    """
    text = str(current_user_input or "").strip()
    m = re.match(r"^\s*(\d+)\s*$", text)
    if not m:
        return None
    idx = int(m.group(1))
    if idx <= 0:
        return None
    latest_system = ""
    for line in reversed(recent_user_turns or []):
        row = str(line or "").strip()
        if row.startswith("System:"):
            latest_system = row[len("System:") :].strip()
            break
    if not latest_system:
        return None
    options: dict[int, str] = {}
    for ln in latest_system.splitlines():
        part = str(ln).strip()
        mm = re.match(r"^(\d+)\s*[\.\、]\s*(.+)$", part)
        if not mm:
            continue
        options[int(mm.group(1))] = mm.group(2).strip()
    option_text = options.get(idx, "")
    if not option_text:
        return None
    neighbors = set(engine.campus_map.get_node(current_node).neighbors)
    for name in sorted(neighbors, key=len, reverse=True):
        if name and name in option_text:
            return name
    for name in sorted(engine.campus_map.nodes.keys(), key=len, reverse=True):
        if name in neighbors and name in option_text:
            return name
    return None


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
                "is_flying": bool(card.is_flying),
                "move_speed": float(card.move_speed),
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
                    "is_flying": bool(card.is_flying),
                    "move_speed": float(card.move_speed),
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
                    "attack": float(unit.card.attack),
                    "health": float(unit.current_health),
                    "max_health": float(unit.card.health),
                    "attack_speed": str(unit.card.hit_speed),
                    "target_preference": str(unit.card.attack_preference),
                    "card_type": str(unit.card.unit_class),
                    "is_flying": bool(unit.card.is_flying),
                    "move_speed": float(unit.card.move_speed),
                    "is_wartime": bool(unit.is_wartime),
                }
            )
            owners[owner_name] = owners.get(owner_name, 0) + 1
    return {
        "total_units": len(unit_rows),
        "owners": owners,
        "units": unit_rows,
    }


def _build_predefined_events(
    engine: GameEngine,
    current_user_input: str,
    override_location: str | None = None,
) -> list[dict[str, Any]]:
    """
    Build predefined backend-handled events exposed to model as selectable event ids.
    """

    if engine.main_player_name is None:
        return []
    main_name = engine.main_player_name
    state = str(engine.global_config.main_game_state)
    dynamic_states = set(engine.global_config.dynamic_states)
    has_ma_phone = "开场事件:主控已持有马超鹏主手机" in dynamic_states
    main_location = str(override_location or engine.get_role(main_name).current_location)

    _ = current_user_input  # Intent parsing is model-only; backend must not parse natural language.
    events: list[dict[str, Any]] = []

    if (
        float(engine.global_config.current_time_unit) < 5.0
        and main_location == "东教学楼内部"
        and OPENING_FLOW_BRANCH not in dynamic_states
        and OPENING_HANDOFF_DONE not in dynamic_states
        and OPENING_MAIN_PHONE_HELD not in dynamic_states
    ):
        events.append(
            {
                "id": "opening_borrow_hotspot_handoff",
                "title": "借马超鹏热点并触发手机交接（与其同行）",
                "trigger_command": "[game_event.trigger=opening_borrow_hotspot_handoff]",
                "auto_time_advance": 1.0,
                "effects": [
                    "全局消息: 手机被老师没收",
                    "全局消息: 马超鹏把他的手机给你 与你同行",
                    "主控切换为马超鹏手机卡组并进入已安装状态",
                ],
            }
        )

    if (
        DEZHENG_BLUE_DEVICE_SEEN in dynamic_states
        and DEZHENG_BLUE_DEVICE_DESTROYED not in dynamic_states
        and main_location == "德政楼"
        and engine.campus_map.is_node_valid("德政楼")
    ):
        heavy_sources = _collect_heavy_strike_sources(engine, main_name, "德政楼")
        status_text = "可执行" if heavy_sources else "当前缺少重型火力"
        events.append(
            {
                "id": "destroy_dezheng_blue_device_with_heavy",
                "title": f"攻击蓝光装置（{status_text}）",
                "trigger_command": "[game_event.trigger=destroy_dezheng_blue_device_with_heavy]",
                "auto_time_advance": 1.0,
                "requirements": {
                    "heavy_required": (
                        f"attack>={DEZHENG_HEAVY_MIN_ATTACK:g} "
                        f"or consume>={DEZHENG_HEAVY_MIN_CONSUME:g}"
                    ),
                    "current_heavy_sources": heavy_sources,
                },
                "effects": [
                    "德政楼坍塌",
                    "进入紧急状态",
                    "6时间单位后学校爆炸",
                ],
            }
        )

    if (
        DYNAMIC_LZB_DEZHENG_PENDING in dynamic_states
        and engine.campus_map.is_node_valid("德政楼")
        and _is_character_or_role_alive(engine, "李再斌")
    ):
        events.append(
            {
                "id": "lzb_trigger_dezheng_device_blast",
                "title": "李再斌正在尝试引爆德政楼装置（待决）",
                "trigger_command": "[game_event.trigger=lzb_trigger_dezheng_device_blast]",
                "auto_time_advance": 0.0,
                "effects": [
                    "装置被摧毁后德政楼会随之坍塌",
                    "进入紧急状态并开启6时间单位后学校爆炸倒计时",
                    "结界解除",
                ],
            }
        )

    seen_marker, broken_marker = _gate_guard_markers(main_location)
    if (
        seen_marker
        and broken_marker
        and seen_marker in dynamic_states
        and broken_marker not in dynamic_states
    ):
        total_power, sources = _collect_gate_guard_break_power(engine, main_name, main_location)
        status_text = "可执行" if total_power + 1e-9 >= GATE_GUARD_BREAK_MIN_POWER else "战力不足"
        events.append(
            {
                "id": "break_gate_guard_blockade_with_units",
                "title": f"指挥部队强行突破{main_location}保安防线（{status_text}）",
                "trigger_command": "[game_event.trigger=break_gate_guard_blockade_with_units]",
                "auto_time_advance": 1.0,
                "requirements": {
                    "min_troop_power": GATE_GUARD_BREAK_MIN_POWER,
                    "current_troop_power": total_power,
                    "current_sources": sources,
                },
                "effects": [
                    f"{main_location}保安防线被突破",
                    f"允许通过{main_location}执行逃离命令",
                ],
            }
        )

    if INTL_TEACHER_EVENT_PENDING in dynamic_states:
        if (
            main_location == "国际部"
            and engine.campus_map.is_node_valid("国际部")
            and _is_character_or_role_alive(engine, "信息老师")
        ):
            installed_now = str(engine.global_config.main_game_state) == "installed"
            if installed_now:
                effects = [
                    "看清后确认是信息老师",
                    "老师训诫“游戏就是毒品”并当场卸载你的皇室战争",
                    "手机不会被收走，仍由主控持有",
                    "主控 main_game_state -> not_installed",
                    f"{main_name}.holy_water -> 0",
                    "主控在场单位清空",
                    "后续再次下载安装仍需2时间单位",
                    "国际部出口被信息老师封锁",
                ]
            else:
                effects = [
                    "看清后与信息老师进行2时间单位常规对话",
                    "老师劝导近期很多学生沉迷手机游戏，强调“游戏就是毒品，不要下载”",
                    "不会触发卸载（当前游戏未安装）",
                    "国际部出口被信息老师封锁，无法翻出校园",
                ]
            return [
                {
                    "id": "international_it_teacher_reveal_confiscate",
                    "title": "走近看清那道人影",
                    "trigger_command": "[game_event.trigger=international_it_teacher_reveal_confiscate]",
                    "auto_time_advance": 2.0,
                    "effects": effects,
                },
            ]
        return events

    liqinbin_pending_active = (
        CANTEEN_LIQINBIN_PENDING in dynamic_states and CANTEEN_LIQINBIN_DONE not in dynamic_states
    )
    if liqinbin_pending_active:
        if (
            main_location == "食堂"
            and engine.campus_map.is_node_valid("食堂")
            and _is_character_or_role_alive(engine, "李秦彬")
        ):
            events.append(
                {
                    "id": "canteen_liqinbin_remind_and_token",
                    "title": "提醒李秦彬校园异变（耗时1.5）",
                    "trigger_command": "[game_event.trigger=canteen_liqinbin_remind_and_token]",
                    "auto_time_advance": 1.5,
                    "effects": [
                        "李秦彬感谢提醒并给主控手机充值皇室令牌",
                        "主控手机获得“无视排序”效果，可下牌窗口提升为前8张",
                        "该效果仅主控手机生效，队友与敌方不生效",
                    ],
                }
            )

    if (
        CANTEEN_UNIVERSAL_KEY_COLLECTED not in dynamic_states
        and main_location == "食堂"
        and engine.campus_map.is_node_valid("食堂")
    ):
        events.append(
            {
                "id": "canteen_collect_universal_key",
                "title": "在食堂收集万能钥匙（耗时1）",
                "trigger_command": "[game_event.trigger=canteen_collect_universal_key]",
                "auto_time_advance": 1.0,
                "effects": [
                    "获得万能钥匙",
                    "万能钥匙可用于开启小卖部或体育馆铁门",
                ],
            }
        )

    if (
        CANTEEN_UNIVERSAL_KEY_COLLECTED in dynamic_states
        and main_location == "小卖部"
        and engine.campus_map.is_node_valid("小卖部")
        and STORE_GATE_OPENED not in dynamic_states
        and STORE_GATE_BROKEN not in dynamic_states
    ):
        events.append(
            {
                "id": "unlock_store_iron_gate_with_key",
                "title": "使用万能钥匙打开小卖部铁门（耗时1）",
                "trigger_command": "[game_event.trigger=unlock_store_iron_gate_with_key]",
                "auto_time_advance": 1.0,
                "effects": [
                    "小卖部铁门打开",
                    "主控HP恢复至10",
                    "激活魔法零食强化：主控与同行可攻击友方角色（许琪琪除外）拳头强化为2点魔法小范围AOE",
                ],
            }
        )
        heavy_sources = _collect_heavy_strike_sources(engine, main_name, "小卖部")
        status_text = "可执行" if heavy_sources else "当前缺少重型火力"
        events.append(
            {
                "id": "break_store_iron_gate_with_heavy",
                "title": f"用重型单位击破小卖部铁门（耗时2，{status_text}）",
                "trigger_command": "[game_event.trigger=break_store_iron_gate_with_heavy]",
                "auto_time_advance": 2.0,
                "requirements": {
                    "heavy_required": (
                        f"attack>={DEZHENG_HEAVY_MIN_ATTACK:g} "
                        f"or consume>={DEZHENG_HEAVY_MIN_CONSUME:g}"
                    ),
                    "current_heavy_sources": heavy_sources,
                },
                "effects": [
                    "小卖部铁门被击破",
                    "小卖部内部会变成一团糟",
                    "无法获得魔法零食强化",
                ],
            }
        )

    if (
        CANTEEN_UNIVERSAL_KEY_COLLECTED in dynamic_states
        and main_location == "体育馆"
        and engine.campus_map.is_node_valid("体育馆")
        and GYM_GATE_OPENED not in dynamic_states
    ):
        events.append(
            {
                "id": "unlock_gym_iron_gate_with_key",
                "title": "使用万能钥匙打开体育馆铁门（耗时1）",
                "trigger_command": "[game_event.trigger=unlock_gym_iron_gate_with_key]",
                "auto_time_advance": 1.0,
                "effects": [
                    "体育馆铁门打开",
                    "触发校歌间奏沉睡事件",
                    "时间-4（仅时间与trigger时刻变化，角色状态不回退）",
                ],
            }
        )

    if liqinbin_pending_active:
        return events

    # If current client is unusable and no 马超鹏主手机 is held, there is no install event to offer.
    if state == "confiscated" and not has_ma_phone:
        return events

    if state == "installed":
        return events

    if has_ma_phone:
        events.append(
            {
                "id": "install_update_game_with_ma_phone",
                "title": "使用马超鹏主手机下载并安装游戏",
                "trigger_command": "[game_event.trigger=install_update_game_with_ma_phone]",
                "auto_time_advance": 2.0,
                "effects": [
                    "global.main_game_state -> installed",
                    f"{main_name}.holy_water -> 0",
                    f"{main_name}.card_valid -> 4",
                ],
            }
        )
    else:
        events.append(
            {
                "id": "install_update_game_with_own_phone",
                "title": "使用主控当前手机下载并安装游戏",
                "trigger_command": "[game_event.trigger=install_update_game_with_own_phone]",
                "auto_time_advance": 2.0,
                "effects": [
                    "global.main_game_state -> installed",
                    f"{main_name}.holy_water -> 0",
                    f"{main_name}.card_valid -> 4",
                ],
            }
        )
    return events


def _build_scene_events(
    engine: GameEngine,
    current_user_input: str,
    override_location: str | None = None,
) -> list[dict[str, Any]]:
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
    main_location = str(override_location or engine.get_role(main_name).current_location)
    dynamic_states = set(engine.global_config.dynamic_states)
    global_states = set(engine.global_config.global_states)
    events: list[dict[str, Any]] = []

    east_marker = "场景事件:厕所遭遇颜宏帆已触发"
    if (
        now < 5.0
        and engine.global_config.battle_state is None
        and main_location == "东教学楼内部"
        and OPENING_MAIN_PHONE_HELD not in dynamic_states
        and OPENING_FLOW_BRANCH not in dynamic_states
        and OPENING_HANDOFF_DONE not in dynamic_states
    ):
        events.append(
            {
                "id": "opening_phone_choice_window",
                "title": "开局课堂：手机更新方式抉择",
                "scene": "东教学楼内部",
                "priority": "high",
                "trigger_when": "t<5 且主控在东教学楼内部，且开局手机分支尚未完结",
                "should_model_decide_trigger": True,
                "trigger_command": "[scene_event.trigger=opening_phone_choice_window]",
                "related_roles": ["马超鹏"],
                "suggested_intent_examples": [
                    "借马超鹏热点更新",
                    "流量更新",
                    "先不更新",
                ],
                "narrative_hint": (
                    "这是开局关键分支：若选择借马超鹏热点，数学老师会收走主控手机；"
                    "后续课堂骚乱节点马超鹏可能把他的主手机交给你。"
                    "若不借热点（如走流量更新/错过借机窗口），会失去后续邀请马超鹏入队并接管其手机卡组的机会。"
                ),
            }
        )

    if (
        east_marker not in dynamic_states
        and engine.global_config.battle_state is None
        and now <= 5.0
        and main_location == "东教学楼内部"
        and _is_role_alive(engine, "颜宏帆")
    ):
        events.append(
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
                "one_shot_marker": east_marker,
            }
        )

    intl_done = INTL_TEACHER_EVENT_DONE in dynamic_states
    intl_pending = INTL_TEACHER_EVENT_PENDING in dynamic_states
    is_normal_time = ("警报状态" not in global_states) and ("紧急状态" not in global_states)
    if (
        (not intl_done)
        and (not intl_pending)
        and engine.global_config.battle_state is None
        and main_location == "国际部"
        and engine.campus_map.is_node_valid("国际部")
        and is_normal_time
        and now <= float(engine.story_setting.alert_trigger_time)
        and _is_character_or_role_alive(engine, "信息老师")
    ):
        events.append(
            {
                "id": "international_it_teacher_encounter",
                "title": "国际部走廊出现熟悉人影",
                "scene": "国际部",
                "priority": "high",
                "trigger_when": "主控位于国际部，国际部未被摧毁，且处于警报前的正常时间",
                "should_model_decide_trigger": True,
                "trigger_command": "[scene_event.trigger=international_it_teacher_encounter]",
                "suggested_intent_examples": [
                    "走近那道模糊的人影",
                    "停下脚步观察国际部走廊",
                    "试着看清对方是谁",
                ],
                "narrative_hint": (
                    "触发后先表现为‘距离较远看不清脸，只看到熟悉人影’。"
                    "不要提供攻击选项；引导玩家决定是否走近看清。"
                    "一旦玩家选择看清，应触发既定事件完成老师介入结算。"
                    "老师只会卸载游戏，不会收走手机。"
                ),
                "one_shot_marker": INTL_TEACHER_EVENT_DONE,
            }
        )
    if (
        (SOUTH_BUILDING_CHENLUO_DONE not in dynamic_states)
        and engine.global_config.battle_state is None
        and main_location == "南教学楼"
        and engine.campus_map.is_node_valid("南教学楼")
        and now < 10.0
        and _is_character_or_role_alive(engine, "陈洛")
    ):
        events.append(
            {
                "id": "south_building_chenluo_heal_encounter",
                "title": "南教学楼遇到陈洛",
                "scene": "南教学楼",
                "priority": "high",
                "trigger_when": "主控位于南教学楼且当前时间<10，且陈洛仍在场",
                "should_model_decide_trigger": True,
                "trigger_command": "[scene_event.trigger=south_building_chenluo_heal_encounter]",
                "suggested_intent_examples": [
                    "进入南教学楼后看到熟悉同学",
                    "靠近那个人影并确认身份",
                    "请求对方帮忙治疗",
                ],
                "narrative_hint": (
                    "触发后直接结算：陈洛用他的手机对主控施放治疗法术，主控生命+3，"
                    "随后陈洛离开校园并不再参与后续剧情。"
                ),
                "one_shot_marker": SOUTH_BUILDING_CHENLUO_DONE,
            }
        )
    if (
        (DEZHENG_BLUE_DEVICE_SEEN not in dynamic_states)
        and (DEZHENG_BLUE_DEVICE_DESTROYED not in dynamic_states)
        and engine.global_config.battle_state is None
        and main_location == "德政楼"
        and engine.campus_map.is_node_valid("德政楼")
    ):
        events.append(
            {
                "id": "dezheng_blue_device_observation",
                "title": "德政楼出现笼罩校园的蓝光装置",
                "scene": "德政楼",
                "priority": "high",
                "trigger_when": "主控位于德政楼且德政楼仍完好",
                "should_model_decide_trigger": True,
                "trigger_command": "[scene_event.trigger=dezheng_blue_device_observation]",
                "suggested_intent_examples": [
                    "查看德政楼中央的奇怪装置",
                    "靠近蓝光源头确认结构",
                    "检查发出蓝光的设备",
                ],
                "narrative_hint": (
                    "触发后应明确描述：装置发出笼罩全校的蓝光，末端与德政楼结构耦合。"
                    "引导玩家可尝试攻击该装置；只有重型打击（如电磁炮、火球等）才可能击毁。"
                    "务必说明：装置一旦被摧毁，德政楼会随之坍塌。"
                ),
                "one_shot_marker": DEZHENG_BLUE_DEVICE_SEEN,
            }
        )
    guard_seen_marker, guard_broken_marker = _gate_guard_markers(main_location)
    if (
        guard_seen_marker
        and guard_broken_marker
        and guard_seen_marker not in dynamic_states
        and guard_broken_marker not in dynamic_states
        and engine.global_config.battle_state is None
    ):
        events.append(
            {
                "id": "gate_guard_blockade_observation",
                "title": f"{main_location}出口被保安死板阻拦",
                "scene": main_location,
                "priority": "high",
                "trigger_when": f"主控位于{main_location}且该出口保安防线尚未突破",
                "should_model_decide_trigger": True,
                "trigger_command": "[scene_event.trigger=gate_guard_blockade_observation]",
                "suggested_intent_examples": [
                    "靠近门口准备离开",
                    "查看出口情况",
                    "和保安交涉",
                ],
                "narrative_hint": (
                    "保安行为极其死板，任何口头说服都无效。"
                    "不要主动把“强行突破保安”作为明确选项给玩家；"
                    "只有玩家主动提出攻击/冲破时，才考虑推进强行突破分支。"
                ),
                "one_shot_marker": guard_seen_marker,
            }
        )
    if (
        CANTEEN_LIQINBIN_PENDING not in dynamic_states
        and CANTEEN_LIQINBIN_DONE not in dynamic_states
        and engine.global_config.battle_state is None
        and main_location == "食堂"
        and engine.campus_map.is_node_valid("食堂")
        and _is_character_or_role_alive(engine, "李秦彬")
    ):
        events.append(
            {
                "id": "canteen_liqinbin_prompt",
                "title": "食堂角落里低头吃饭的李秦彬",
                "scene": "食堂",
                "priority": "high",
                "trigger_when": "主控位于食堂，且李秦彬仍在场",
                "should_model_decide_trigger": True,
                "trigger_command": "[scene_event.trigger=canteen_liqinbin_prompt]",
                "suggested_intent_examples": [
                    "走近食堂里的那个同学",
                    "提醒他外面出事了",
                    "先问他知不知道发生了什么",
                ],
                "narrative_hint": (
                    "触发后系统应明确询问玩家是否要提醒他校园异变。"
                    "若玩家选择提醒，可触发既定事件：耗时1.5，获得主控手机专属皇室令牌。"
                ),
                "one_shot_marker": CANTEEN_LIQINBIN_PENDING,
            }
        )
    if (
        CANTEEN_UNIVERSAL_KEY_COLLECTED not in dynamic_states
        and CANTEEN_UNIVERSAL_KEY_PENDING not in dynamic_states
        and engine.global_config.battle_state is None
        and main_location == "食堂"
        and engine.campus_map.is_node_valid("食堂")
    ):
        events.append(
            {
                "id": "canteen_universal_key_prompt",
                "title": "食堂角落里一把可疑的万能钥匙",
                "scene": "食堂",
                "priority": "high",
                "trigger_when": "主控位于食堂且尚未取得万能钥匙",
                "should_model_decide_trigger": True,
                "trigger_command": "[scene_event.trigger=canteen_universal_key_prompt]",
                "suggested_intent_examples": [
                    "查看食堂角落的反光物件",
                    "捡起那把钥匙",
                    "问这把钥匙能开哪里",
                ],
                "narrative_hint": (
                    "触发后应提示玩家：可花费1时间单位收集万能钥匙。"
                    "万能钥匙可用于开启小卖部或体育馆铁门。"
                ),
                "one_shot_marker": CANTEEN_UNIVERSAL_KEY_PENDING,
            }
        )
    if (
        STORE_GATE_OPENED not in dynamic_states
        and STORE_GATE_BROKEN not in dynamic_states
        and STORE_GATE_SEEN not in dynamic_states
        and engine.global_config.battle_state is None
        and main_location == "小卖部"
        and engine.campus_map.is_node_valid("小卖部")
    ):
        events.append(
            {
                "id": "store_iron_gate_observation",
                "title": "小卖部铁门紧闭",
                "scene": "小卖部",
                "priority": "high",
                "trigger_when": "主控位于小卖部且铁门未打开",
                "should_model_decide_trigger": True,
                "trigger_command": "[scene_event.trigger=store_iron_gate_observation]",
                "suggested_intent_examples": [
                    "检查小卖部铁门",
                    "尝试寻找开门方法",
                    "观察门缝里的情况",
                ],
                "narrative_hint": (
                    "触发后应提示玩家小卖部铁门被锁。"
                    "若玩家主动提出强攻，可按重型破门逻辑判定（耗时2）。"
                ),
                "one_shot_marker": STORE_GATE_SEEN,
            }
        )
    if (
        GYM_GATE_OPENED not in dynamic_states
        and GYM_GATE_SEEN not in dynamic_states
        and engine.global_config.battle_state is None
        and main_location == "体育馆"
        and engine.campus_map.is_node_valid("体育馆")
    ):
        events.append(
            {
                "id": "gym_iron_gate_observation",
                "title": "体育馆铁门卡死",
                "scene": "体育馆",
                "priority": "high",
                "trigger_when": "主控位于体育馆且铁门尚未打开",
                "should_model_decide_trigger": True,
                "trigger_command": "[scene_event.trigger=gym_iron_gate_observation]",
                "suggested_intent_examples": [
                    "检查体育馆门锁",
                    "尝试进入体育馆",
                    "寻找开门办法",
                ],
                "narrative_hint": (
                    "触发后应提示玩家体育馆铁门无法直接打开。"
                ),
                "one_shot_marker": GYM_GATE_SEEN,
            }
        )
    if (
        engine.global_config.battle_state is not None
        and main_location in {"正门", "后门", "国际部"}
    ):
        events.append(
            {
                "id": "battle_escape_blocked_notice",
                "title": "交战中试图逃离会被拦下",
                "scene": main_location,
                "priority": "high",
                "trigger_when": "主控正在交战且位于门口/国际部边缘",
                "should_model_decide_trigger": True,
                "trigger_command": "[scene_event.trigger=battle_escape_blocked_notice]",
                "suggested_intent_examples": [
                    "冲向门口逃离",
                    "翻出去",
                    "立刻离开校园",
                ],
                "narrative_hint": "正在交战时不可直接逃离校园，试图逃离会被拦下并需先脱离战斗。",
            }
        )
    return events


def _is_role_alive(engine: GameEngine, role_name: str) -> bool:
    if role_name in engine.character_profiles:
        if engine.get_character_profile(role_name).status != "存活":
            return False
    if role_name in engine.campus_map.roles:
        return engine.get_role(role_name).health > 0
    return False


def _is_role_active_for_context(engine: GameEngine, role_name: str) -> bool:
    """
    Context visibility rule:
    - Hide dead / left-campus roles from prompt context and scene blocks.
    """
    if role_name in engine.character_profiles:
        if engine.get_character_profile(role_name).status != "存活":
            return False
    if role_name not in engine.campus_map.roles:
        return False
    return engine.get_role(role_name).health > 0


def _is_character_or_role_alive(engine: GameEngine, role_name: str) -> bool:
    """
    Return alive unless either profile/role explicitly indicates death.
    """

    exists = False
    if role_name in engine.character_profiles:
        exists = True
        if engine.get_character_profile(role_name).status != "存活":
            return False
    if role_name in engine.campus_map.roles:
        exists = True
        if engine.get_role(role_name).health <= 0:
            return False
    return exists


def _collect_heavy_strike_sources(engine: GameEngine, main_name: str, node_name: str) -> list[str]:
    """
    Return active heavy deployed cards currently present at the given node.
    """

    main_player = engine.get_player(main_name)
    rows: list[str] = []
    for unit in main_player.list_active_units():
        if unit.node_name != node_name:
            continue
        if (
            float(unit.card.attack) < DEZHENG_HEAVY_MIN_ATTACK
            and float(unit.card.consume) < DEZHENG_HEAVY_MIN_CONSUME
        ):
            continue
        rows.append(f"{unit.owner_name}:{unit.card.name}")
    return sorted(rows)


def _gate_guard_markers(node_name: str) -> tuple[str | None, str | None]:
    if node_name == "正门":
        return GATE_GUARD_SEEN_FRONT, GATE_GUARD_BROKEN_FRONT
    if node_name == "后门":
        return GATE_GUARD_SEEN_BACK, GATE_GUARD_BROKEN_BACK
    return None, None


def _collect_gate_guard_break_power(engine: GameEngine, main_name: str, node_name: str) -> tuple[float, list[str]]:
    player = engine.get_player(main_name)
    total_power = 0.0
    sources: list[str] = []
    for unit in player.list_active_units():
        if unit.node_name != node_name:
            continue
        if str(unit.card.unit_class) == "spell":
            continue
        atk = float(unit.card.attack)
        if atk <= 0:
            continue
        total_power += atk
        sources.append(f"{unit.owner_name}:{unit.card.name}(atk={atk:g})")
    return total_power, sorted(sources)
