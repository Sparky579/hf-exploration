"""
Module purpose:
- Compile simple string commands into game operations and queue messages.

Core design:
- `move` and `deploy` commands are queued in `message_queue`.
- Most state updates are applied immediately when compiling.
- `queue.flush=true` executes queued messages in order.
- Every command is recorded into `command_logs` with execution time and result.

Supported syntax summary:
- Comment/blank: lines starting with `#` or empty lines are ignored.
- Optional wrapper: one command can be wrapped as `[<command>]`.
- Assignment: `left=right`
- Append/remove text: `left+=text`, `left-=text` for text lists.
- Numeric delta: `left+=number`, `left-=number` for numeric fields.

Queue commands:
- `<role>.move=<node>`
- `<role>.deploy=<card_name>`
- `<role>.deploy=<card_name>@<node>`
- `queue.flush=true`
- `queue.clear=true`

Immediate state commands:
- `time.advance=<number>` (must be multiple of 0.5)
- `global.battle=<target_role_name|none>`
- `global.emergency=<true|false>`
- `global.main_player=<player_name>`
- `global.main_game_state=<installed|downloading|not_installed|confiscated>`
- `global.team=<name1,name2,...>`
- `map.<node>.valid=<true|false>`
- `<role>.location=<node>`
- `<role>.escape=<node>`
- `<role>.discover=<companion_name>`
- `<role>.invite=<companion_name>`
- `<role>.health=<number>`
- `<role>.holy_water=<number>`
- `<role>.battle=<target_role_name|none>`
- `<role>.card_valid=<int>`
- `<role>.card_deck=<card1,...,card8>`
- `<role>.deck=<card1,...,card8>`
- `<role>.nearby_units=<unitA:full,unitB:damaged>`
- `<role>.nearby_unit.<unit_name>=<full|damaged|dead>`
- `<role>.nearby_unit.<unit_name>.health=<number>`
- `<role>.unit.<unit_id>.health=<number>` (<=0 means dead, remove from active list)
- `trigger.add=<trigger sentence>`
- `trigger.remove=<id_or_text>`
- `trigger.clear=true`
- `scene_event.trigger=<event_id>`
- `game_event.trigger=<event_id>`
- `event.rocket_launch=<building_or_node_name>`

Companion commands:
- `companion.<name>.deploy=<card_name>`
- `companion.<name>.deploy=<card_name>@<node>`
- `companion.<name>.discovered=<true|false>`
- `companion.<name>.in_team=<true|false>`
- `companion.<name>.holy_water=<number>`
- `companion.<name>.affection=<number>`
- `companion.<name>.noticed_by=<hostile1,hostile2,...>`
- `companion.<name>.noticed_by+=<hostile>`
- `companion.<name>.noticed_by-=<hostile>`

Text list commands:
- `global.state+=<text>` / `global.state-=<text>`
- `<role>.state+=<text>` / `<role>.state-=<text>`
- `character.<name>.history+=<text>` / `character.<name>.history-=<text>`
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .constants import (
    DYNAMIC_GYM_INTERLUDE_DONE,
    GLOBAL_STATE_GAME_INSTALL_DONE,
    GLOBAL_STATE_MAGIC_SNACK_BUFF,
    GLOBAL_STATE_UNIVERSAL_KEY_OWNED,
)
from .engine import GameEngine

INTL_TEACHER_EVENT_PENDING = "场景事件:国际部信息老师待抉择"
INTL_TEACHER_EVENT_DONE = "场景事件:国际部信息老师已结局"
INTL_TEACHER_EVENT_CONFISCATED = "场景事件:国际部信息老师卸载游戏"
INTL_TEACHER_EXIT_BLOCKED = "场景事件:国际部信息老师封锁国际部出口"
OPENING_MAIN_PHONE_HELD = "开场事件:主控已持有马超鹏主手机"
SOUTH_BUILDING_CHENLUO_DONE = "场景事件:南教学楼遭遇陈洛已触发"
DEZHENG_BLUE_DEVICE_SEEN = "场景事件:德政楼蓝光装置已发现"
DEZHENG_BLUE_DEVICE_DESTROYED = "场景事件:德政楼蓝光装置已摧毁"
CANTEEN_LIQINBIN_PENDING = "场景事件:食堂李秦彬提醒待抉择"
CANTEEN_LIQINBIN_DONE = "场景事件:食堂李秦彬提醒已完成"
MAIN_ROYALE_TOKEN_ACTIVE = "主控手机效果:皇室令牌已激活"
MAIN_ROYALE_TOKEN_FLAG = "flag.main_royale_token_active"
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


@dataclass
class QueueMessage:
    """One queued action to be executed later."""

    action: str
    role_name: str
    payload: dict[str, str]
    source_line: str


@dataclass
class CommandLog:
    """One command execution record."""

    time_unit: float
    command: str
    status: str
    detail: str


class CommandPipeline:
    """Compile command text and drive queue/state operations."""

    def __init__(self, engine: GameEngine) -> None:
        self.engine = engine
        self.message_queue: list[QueueMessage] = []
        self.runtime_messages: list[str] = []
        self.command_logs: list[CommandLog] = []

    def compile_script(self, script: str) -> list[str]:
        """Compile and apply one multi-line script."""

        line_count = 0
        for raw in script.splitlines():
            line_count += 1
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            self.compile_line(line)
        self.runtime_messages.append(f"compiled {line_count} lines")
        return list(self.runtime_messages)

    def compile_line(self, line: str) -> None:
        """Compile and apply one line."""

        line = self._normalize_bracket_command(line)
        try:
            if "+=" in line:
                left, right = line.split("+=", 1)
                self._apply_plus(left.strip(), right.strip())
                self._append_log(line, "ok", "plus-assignment applied")
                return
            if "-=" in line:
                left, right = line.split("-=", 1)
                self._apply_minus(left.strip(), right.strip())
                self._append_log(line, "ok", "minus-assignment applied")
                return
            if "=" in line:
                left, right = line.split("=", 1)
                self._apply_assign(left.strip(), right.strip(), line)
                self._append_log(line, "ok", "assignment applied")
                return
            raise ValueError(f"invalid command syntax: {line}")
        except Exception as exc:
            self._append_log(line, "error", str(exc))
            raise
        finally:
            # Keep main-player holy_water/card_valid aligned with global runtime gates
            # (install state + token effects), even if model emits conflicting commands.
            self.engine.sync_main_player_runtime_gates()

    def flush_queue(self) -> list[str]:
        """Execute all queued move/deploy messages in order."""

        executed = 0
        while self.message_queue:
            msg = self.message_queue.pop(0)
            if msg.action == "move":
                self.engine.issue_move(msg.role_name, msg.payload["target_node"])
                self.runtime_messages.append(
                    f"queued move accepted: {msg.role_name} -> {msg.payload['target_node']}"
                )
                self._append_log(msg.source_line, "ok", "queued move accepted")
            elif msg.action == "deploy":
                player = self.engine.get_player(msg.role_name)
                card_name = msg.payload.get("card_name")
                node_name = msg.payload.get("node_name")
                player.deploy_from_deck(card_name=card_name, node_name=node_name)
                self.runtime_messages.append(
                    f"queued deploy executed: {msg.role_name} card={card_name or 'TOP'}"
                )
                self._append_log(msg.source_line, "ok", "queued deploy executed")
            else:
                raise ValueError(f"unknown queue action: {msg.action}")
            executed += 1
        self.runtime_messages.append(f"queue flushed: {executed} message(s)")
        return list(self.runtime_messages)

    def get_recent_logs(self, limit: int = 15) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        rows = self.command_logs[-limit:]
        return [
            {
                "time": row.time_unit,
                "command": row.command,
                "status": row.status,
                "detail": row.detail,
            }
            for row in rows
        ]

    def _append_log(self, command: str, status: str, detail: str) -> None:
        self.command_logs.append(
            CommandLog(
                time_unit=float(self.engine.global_config.current_time_unit),
                command=command,
                status=status,
                detail=detail,
            )
        )

    def _apply_plus(self, left: str, right: str) -> None:
        if left == "global.state":
            self.engine.add_global_dynamic_state(right)
            self.runtime_messages.append("global dynamic state appended")
            return
        if left in ("global.team", "global.team_companions"):
            self.engine.set_companion_in_team(right, True)
            self.runtime_messages.append(f"team companion added: {right}")
            return
        if left.startswith("character.") and left.endswith(".history"):
            name = left[len("character.") : -len(".history")]
            self.engine.add_character_history(name, right)
            self.runtime_messages.append(f"character history appended: {name}")
            return
        if left.startswith("companion.") and left.endswith(".noticed_by"):
            name = left[len("companion.") : -len(".noticed_by")]
            self.engine.add_companion_noticer(name, right)
            self.runtime_messages.append(f"companion noticer added: {name} <- {right}")
            return
        if left.endswith(".state"):
            role_name = self._resolve_role_name_alias(left[:-6])
            self.engine.add_role_dynamic_state(role_name, right)
            self.runtime_messages.append(f"role dynamic state appended: {role_name}")
            return
        if left.endswith(".nearby_units"):
            role_name = self._resolve_role_name_alias(left[: -len(".nearby_units")])
            items = self._parse_nearby_units(right)
            self._merge_nearby_units(role_name, items)
            self.runtime_messages.append(f"nearby_units merged: {role_name}")
            return
        self._apply_numeric_delta(left, right, sign=1.0)

    def _apply_minus(self, left: str, right: str) -> None:
        if left == "global.state":
            self.engine.global_config.remove_dynamic_state(right)
            self.runtime_messages.append("global dynamic state removed")
            return
        if left in ("global.team", "global.team_companions"):
            self.engine.set_companion_in_team(right, False)
            self.runtime_messages.append(f"team companion removed: {right}")
            return
        if left.startswith("character.") and left.endswith(".history"):
            name = left[len("character.") : -len(".history")]
            self.engine.remove_character_history(name, right)
            self.runtime_messages.append(f"character history removed: {name}")
            return
        if left.startswith("companion.") and left.endswith(".noticed_by"):
            name = left[len("companion.") : -len(".noticed_by")]
            self.engine.remove_companion_noticer(name, right)
            self.runtime_messages.append(f"companion noticer removed: {name} -/-> {right}")
            return
        if left.endswith(".state"):
            role_name = self._resolve_role_name_alias(left[:-6])
            role = self.engine.get_role(role_name)
            role.remove_dynamic_state(right)
            self.runtime_messages.append(f"role dynamic state removed: {role_name}")
            return
        if left.endswith(".nearby_units"):
            role_name = self._resolve_role_name_alias(left[: -len(".nearby_units")])
            unit_names = self._parse_nearby_unit_names(right)
            self._prune_nearby_units(role_name, unit_names)
            self.runtime_messages.append(f"nearby_units pruned: {role_name}")
            return
        self._apply_numeric_delta(left, right, sign=-1.0)

    def _merge_nearby_units(self, role_name: str, items: dict[str, str]) -> None:
        """
        Incremental nearby-unit merge semantics:
        - For player owners, `nearby_units+=<card>:full|damaged` can materialize a runtime deploy
          (with normal holy-water/card-window checks) when no same-name unit is currently nearby.
        - For non-player roles, keep narrative-only status tags.
        """
        self._assert_role_location_valid_for_internal_action(role_name, "nearby_units")
        role = self.engine.get_role(role_name)
        is_player_owner = role_name in self.engine.players
        player = self.engine.get_player(role_name) if is_player_owner else None
        current_node = role.current_location

        for unit_name, status in items.items():
            if status == "dead":
                self._prune_nearby_units(role_name, [unit_name])
                continue

            if is_player_owner and (unit_name in (player.available_cards if player else {})):
                candidates = [
                    u
                    for u in (player.list_active_units() if player else [])
                    if u.card.name == unit_name and u.node_name == current_node
                ]
                if not candidates:
                    try:
                        player.deploy_from_deck(card_name=unit_name, node_name=current_node)
                    except Exception as exc:  # noqa: BLE001 - keep parser errors explicit
                        raise ValueError(f"nearby_units add failed for {unit_name}: {exc}") from exc
                    candidates = [
                        u
                        for u in player.list_active_units()
                        if u.card.name == unit_name and u.node_name == current_node
                    ]
                if candidates:
                    candidates.sort(key=lambda u: (float(u.deployed_time), u.unit_id))
                    target = candidates[0]
                    max_hp = float(target.card.health)
                    if status == "damaged":
                        target.current_health = min(float(target.current_health), max(1.0, max_hp * 0.5))
                        role.set_nearby_unit_status(unit_name, "damaged")
                    else:
                        if float(target.current_health) <= 0:
                            target.current_health = max_hp
                        role.set_nearby_unit_status(unit_name, "full")
                    continue

            role.set_nearby_unit_status(unit_name, status)

    def _prune_nearby_units(self, role_name: str, unit_names: list[str]) -> None:
        self._assert_role_location_valid_for_internal_action(role_name, "nearby_units")
        role = self.engine.get_role(role_name)
        is_player_owner = role_name in self.engine.players
        player = self.engine.get_player(role_name) if is_player_owner else None
        current_node = role.current_location

        for unit_name in unit_names:
            role.set_nearby_unit_status(unit_name, "dead")
            if not is_player_owner or player is None:
                continue
            candidates = [u for u in player.list_active_units() if u.card.name == unit_name]
            if not candidates:
                continue
            local = [u for u in candidates if u.node_name == current_node]
            pool = local if local else candidates
            pool.sort(key=lambda u: (float(u.current_health), float(u.deployed_time)))
            player.remove_unit(pool[0].unit_id)

    def _apply_assign(self, left: str, right: str, source_line: str) -> None:
        if left == "queue.flush":
            if self._parse_bool(right):
                self.flush_queue()
            return
        if left == "queue.clear":
            if self._parse_bool(right):
                self.message_queue.clear()
                self.runtime_messages.append("queue cleared")
            return
        if left == "time.advance":
            value = self._parse_float(right)
            self._assert_half_step(value)
            self.engine.advance_time(value)
            self.runtime_messages.append(f"time advanced: +{value}")
            return
        if left == "global.battle":
            battle_target = self._parse_battle_value(right)
            self.engine.set_battle_state(battle_target)
            self.runtime_messages.append(f"global battle set: {battle_target}")
            return
        if left == "global.emergency":
            self.engine.set_emergency_phase(self._parse_bool(right))
            self.runtime_messages.append(f"global emergency set: {right}")
            return
        if left == "global.main_player":
            self.engine.set_main_player(right)
            self.runtime_messages.append(f"global main_player set: {right}")
            return
        if left in ("global.main_game_state", "global.phone_state", "global.client_state"):
            self.engine.set_main_game_state(right)
            self.runtime_messages.append(f"{left} set: {right}")
            return
        if left in ("global.team", "global.team_companions"):
            members = [name.strip() for name in right.split(",") if name.strip()]
            self.engine.set_team_companions(members)
            self.runtime_messages.append("global team replaced")
            return
        if left == "trigger.add":
            item = self.engine.global_config.add_scripted_trigger(right)
            self.runtime_messages.append(f"trigger added: #{item['id']}")
            return
        if left == "trigger.remove":
            removed = self.engine.global_config.remove_scripted_trigger(right)
            if not removed:
                raise ValueError(f"trigger not found: {right}")
            self.runtime_messages.append(f"trigger removed: {right}")
            return
        if left == "trigger.clear":
            if self._parse_bool(right):
                self.engine.global_config.clear_scripted_triggers()
                self.runtime_messages.append("trigger list cleared")
            return
        if left == "scene_event.trigger":
            self._apply_scene_event_trigger(right.strip())
            self.runtime_messages.append(f"scene event triggered: {right.strip()}")
            return
        if left == "game_event.trigger":
            self._apply_game_event_trigger(right.strip())
            self.runtime_messages.append(f"game event triggered: {right.strip()}")
            return
        if left == "event.rocket_launch":
            target = right.strip()
            if not target:
                raise ValueError("event.rocket_launch target must be non-empty.")
            now = float(self.engine.global_config.current_time_unit)
            self.engine.global_config.add_dynamic_state(
                f"提示：你听到火箭升空声，{target}将在1时间单位后坍塌"
            )
            trigger_text = f"角色:系统|时间{now + 1:g} 若火箭命中{target} 则 建筑倒塌:{target}"
            item = self.engine.global_config.add_scripted_trigger(trigger_text)
            self.runtime_messages.append(f"rocket warning created trigger: #{item['id']}")
            return

        if left.startswith("map.") and left.endswith(".valid"):
            node_name = left[len("map.") : -len(".valid")]
            self.engine.set_node_valid(node_name, self._parse_bool(right))
            self.runtime_messages.append(f"map node valid set: {node_name}={right}")
            return

        if left.startswith("character."):
            self._apply_character_assign(left, right)
            return
        if left.startswith("companion."):
            self._apply_companion_assign(left, right)
            return

        left_parts = left.split(".")
        if len(left_parts) < 2:
            raise ValueError(f"invalid target: {left}")
        role_name = self._resolve_role_name_alias(left_parts[0])
        field = left_parts[1]
        role = self.engine.ensure_runtime_role(role_name)

        if field == "move":
            self.message_queue.append(
                QueueMessage(
                    action="move",
                    role_name=role_name,
                    payload={"target_node": right},
                    source_line=source_line,
                )
            )
            self.runtime_messages.append(f"move queued: {role_name} -> {right}")
            return
        if field == "deploy":
            self._assert_role_location_valid_for_internal_action(role_name, "deploy")
            card_name, node_name = self._parse_deploy_payload(right)
            payload = {"card_name": card_name}
            if node_name:
                payload["node_name"] = node_name
            self.message_queue.append(
                QueueMessage(
                    action="deploy",
                    role_name=role_name,
                    payload=payload,
                    source_line=source_line,
                )
            )
            self.runtime_messages.append(f"deploy queued: {role_name} card={card_name}")
            return
        if field == "location":
            self.engine.set_role_location(role_name, right)
            self.runtime_messages.append(f"location set: {role_name} -> {right}")
            return
        if field == "escape":
            self.engine.attempt_escape(role_name, right)
            self.runtime_messages.append(f"escape success: {role_name} via {right}")
            return
        if field == "discover":
            self.engine.discover_companion(role_name, right)
            self.runtime_messages.append(f"discover success: {role_name} found {right}")
            return
        if field == "invite":
            self.engine.invite_companion(role_name, right)
            self.runtime_messages.append(f"invite success: {role_name} invited {right}")
            return
        if field == "health":
            self.engine.set_role_health(role_name, self._parse_float(right))
            self.runtime_messages.append(f"health set: {role_name}")
            return
        if field == "holy_water":
            self.engine.set_player_holy_water(role_name, self._parse_float(right))
            self.runtime_messages.append(f"holy_water set: {role_name}")
            return
        if field == "battle":
            self.engine.set_role_battle_target(role_name, self._parse_optional_string(right))
            self.runtime_messages.append(f"role battle target set: {role_name}")
            return
        if field == "card_valid":
            player = self.engine.get_player(role_name)
            player.set_card_valid(int(right))
            self.runtime_messages.append(f"card_valid set: {role_name} -> {right}")
            return
        if field in ("card_deck", "deck"):
            deck = [x.strip() for x in right.split(",") if x.strip()]
            self.engine.set_player_card_deck(role_name, deck)
            self.runtime_messages.append(f"card_deck set: {role_name}")
            return
        if field == "nearby_units":
            self._assert_role_location_valid_for_internal_action(role_name, "nearby_units")
            role.replace_nearby_units(self._parse_nearby_units(right))
            self.runtime_messages.append(f"nearby_units replaced: {role_name}")
            return
        if field == "nearby_unit" and len(left_parts) >= 4 and left_parts[-1] == "health":
            self._assert_role_location_valid_for_internal_action(role_name, "nearby_unit.health")
            unit_name = ".".join(left_parts[2:-1]).strip()
            if not unit_name:
                raise ValueError("nearby_unit health command requires unit name.")
            self._set_named_nearby_unit_health(role_name, unit_name, self._parse_float(right))
            self.runtime_messages.append(f"nearby_unit health set: {role_name}.{unit_name}")
            return
        if field == "nearby_unit" and len(left_parts) >= 3:
            self._assert_role_location_valid_for_internal_action(role_name, "nearby_unit")
            unit_name = ".".join(left_parts[2:])
            role.set_nearby_unit_status(unit_name, self._normalize_nearby_status(right))
            self.runtime_messages.append(f"nearby_unit status set: {role_name}.{unit_name}={right}")
            return
        if field == "unit" and len(left_parts) == 4 and left_parts[3] == "health":
            self._assert_role_location_valid_for_internal_action(role_name, "unit.health")
            unit_id = left_parts[2]
            self._set_runtime_unit_health(role_name, unit_id, self._parse_float(right))
            self.runtime_messages.append(f"runtime unit health set: {role_name}.{unit_id}")
            return
        raise ValueError(f"unsupported assignment command: {left}={right}")

    def _apply_character_assign(self, left: str, right: str) -> None:
        parts = left.split(".")
        if len(parts) != 3:
            raise ValueError(f"invalid character command target: {left}")
        _, name, field = parts
        if field == "status":
            self.engine.set_character_status(name, right)
            if str(right).strip() == "死亡" and name in self.engine.campus_map.roles:
                self.engine.set_role_health(name, 0.0)
            self.runtime_messages.append(f"character status set: {name} -> {right}")
            return
        if field == "deck":
            deck = [x.strip() for x in right.split(",") if x.strip()]
            if name in self.engine.character_profiles:
                self.engine.set_character_deck(name, deck)
                self.runtime_messages.append(f"character deck set: {name}")
                return
            if name in self.engine.players:
                self.engine.set_player_card_deck(name, deck)
                self.runtime_messages.append(f"player card_deck set via character alias: {name}")
                return
            raise KeyError(f"character profile not found: {name}")
        if field == "description":
            self.engine.set_character_description(name, right)
            self.runtime_messages.append(f"character description set: {name}")
            return
        raise ValueError(f"unsupported character command: {left}={right}")

    def _apply_companion_assign(self, left: str, right: str) -> None:
        parts = left.split(".")
        if len(parts) != 3:
            raise ValueError(f"invalid companion command target: {left}")
        _, name, field = parts
        if field == "deploy":
            actor = self.engine.main_player_name
            if actor is None:
                raise ValueError("global main_player must be set before companion deploy.")
            card_name, node_name = self._parse_deploy_payload(right)
            self.engine.deploy_companion_card(actor, name, card_name, node_name=node_name)
            self.runtime_messages.append(f"companion deploy executed: {name} card={card_name}")
            return
        if field == "discovered":
            self.engine.set_companion_discovered(name, self._parse_bool(right))
            self.runtime_messages.append(f"companion discovered set: {name}")
            return
        if field == "in_team":
            self.engine.set_companion_in_team(name, self._parse_bool(right))
            self.runtime_messages.append(f"companion in_team set: {name}")
            return
        if field == "holy_water":
            self.engine.set_companion_holy_water(name, self._parse_float(right))
            self.runtime_messages.append(f"companion holy_water set: {name}")
            return
        if field == "affection":
            self.engine.set_companion_affection(name, self._parse_float(right))
            self.runtime_messages.append(f"companion affection set: {name}")
            return
        if field == "noticed_by":
            hostiles = [x.strip() for x in right.split(",") if x.strip()]
            self.engine.set_companion_noticers(name, hostiles)
            self.runtime_messages.append(f"companion noticed_by set: {name}")
            return
        raise ValueError(f"unsupported companion command: {left}={right}")

    def _set_runtime_unit_health(self, role_name: str, unit_id: str, value: float) -> None:
        player = self.engine.get_player(role_name)
        if unit_id not in player.active_units:
            raise KeyError(f"active unit not found: {unit_id}")
        if value <= 0:
            player.remove_unit(unit_id)
            return
        player.active_units[unit_id].current_health = value

    def _apply_numeric_delta(self, left: str, right: str, sign: float) -> None:
        delta = self._parse_float(right) * sign
        if left == "time.advance":
            if delta < 0:
                raise ValueError("time.advance-= is not supported.")
            self._assert_half_step(delta)
            self.engine.advance_time(delta)
            self.runtime_messages.append(f"time advanced: +{delta}")
            return

        if left.startswith("companion.") and left.endswith(".affection"):
            name = left[len("companion.") : -len(".affection")]
            self.engine.add_companion_affection(name, delta)
            self.runtime_messages.append(f"companion affection changed: {name} ({delta:+g})")
            return
        if left.startswith("companion.") and left.endswith(".holy_water"):
            name = left[len("companion.") : -len(".holy_water")]
            self.engine.add_companion_holy_water(name, delta)
            self.runtime_messages.append(f"companion holy_water changed: {name} ({delta:+g})")
            return

        left_parts = left.split(".")
        if len(left_parts) < 2:
            raise ValueError(f"unsupported numeric delta command: {left}")
        role_name = self._resolve_role_name_alias(left_parts[0])
        field = left_parts[1]
        role = self.engine.ensure_runtime_role(role_name)

        if field == "health":
            self.engine.set_role_health(role_name, role.health + delta)
            self.runtime_messages.append(f"health changed: {role_name} ({delta:+g})")
            return
        if field == "holy_water":
            player = self.engine.get_player(role_name)
            self.engine.set_player_holy_water(role_name, player.holy_water + delta)
            self.runtime_messages.append(f"holy_water changed: {role_name} ({delta:+g})")
            return
        if field == "card_valid":
            if abs(delta - round(delta)) > 1e-9:
                raise ValueError("card_valid delta must be an integer.")
            player = self.engine.get_player(role_name)
            player.set_card_valid(player.card_valid + int(round(delta)))
            self.runtime_messages.append(f"card_valid changed: {role_name} ({int(round(delta)):+d})")
            return
        if field == "nearby_unit" and len(left_parts) >= 4 and left_parts[-1] == "health":
            self._assert_role_location_valid_for_internal_action(role_name, "nearby_unit.health")
            unit_name = ".".join(left_parts[2:-1]).strip()
            if not unit_name:
                raise ValueError("nearby_unit health command requires unit name.")
            current = self._get_named_nearby_unit_health(role_name, unit_name)
            current_value = float(current) if current is not None else 0.0
            next_health = current_value + delta
            self._set_named_nearby_unit_health(role_name, unit_name, next_health)
            self.runtime_messages.append(f"nearby_unit health changed: {role_name}.{unit_name} ({delta:+g})")
            return
        if field == "unit" and len(left_parts) == 4 and left_parts[3] == "health":
            unit_id = left_parts[2]
            player = self.engine.get_player(role_name)
            if unit_id not in player.active_units:
                raise KeyError(f"active unit not found: {unit_id}")
            next_health = player.active_units[unit_id].current_health + delta
            self._set_runtime_unit_health(role_name, unit_id, next_health)
            self.runtime_messages.append(f"runtime unit health changed: {role_name}.{unit_id} ({delta:+g})")
            return
        raise ValueError(f"unsupported numeric delta command: {left}")

    def _assert_role_location_valid_for_internal_action(self, role_name: str, action_name: str) -> None:
        role = self.engine.get_role(role_name)
        if not self.engine.campus_map.is_node_valid(role.current_location):
            raise ValueError(
                f"cannot execute internal action '{action_name}' at destroyed node: {role.current_location}"
            )

    @staticmethod
    def _parse_bool(text: str) -> bool:
        lowered = text.strip().lower()
        if lowered in ("true", "1", "yes", "on"):
            return True
        if lowered in ("false", "0", "no", "off"):
            return False
        raise ValueError(f"invalid bool value: {text}")

    @staticmethod
    def _parse_float(text: str) -> float:
        try:
            return float(text)
        except ValueError as exc:
            raise ValueError(f"invalid numeric value: {text}") from exc

    @staticmethod
    def _assert_half_step(value: float) -> None:
        doubled = value * 2
        if abs(doubled - round(doubled)) > 1e-9:
            raise ValueError("time.advance must be a multiple of 0.5.")

    @staticmethod
    def _parse_optional_string(text: str) -> str | None:
        lowered = text.strip().lower()
        if lowered in ("none", "null", "", "false", "off", "0"):
            return None
        return text.strip()

    @classmethod
    def _parse_battle_value(cls, text: str) -> str | None:
        lowered = text.strip().lower()
        if lowered in ("none", "null", "", "false", "off", "0"):
            return None
        if lowered in ("true", "on", "1", "yes"):
            raise ValueError("global.battle must be a role name or none; boolean battle is not supported.")
        return text.strip()

    def _apply_scene_event_trigger(self, event_id: str) -> None:
        """
        Apply one known scene event by event id.
        """

        if not event_id:
            raise ValueError("scene_event.trigger requires a non-empty event id.")
        if event_id == "east_toilet_yanhongfan_encounter":
            self._trigger_east_toilet_yanhongfan_encounter()
            return
        if event_id == "opening_phone_choice_window":
            self._trigger_opening_phone_choice_window()
            return
        if event_id == "international_it_teacher_encounter":
            self._trigger_international_it_teacher_encounter()
            return
        if event_id == "south_building_chenluo_heal_encounter":
            self._trigger_south_building_chenluo_heal_encounter()
            return
        if event_id == "dezheng_blue_device_observation":
            self._trigger_dezheng_blue_device_observation()
            return
        if event_id == "gate_guard_blockade_observation":
            self._trigger_gate_guard_blockade_observation()
            return
        if event_id == "canteen_liqinbin_prompt":
            self._trigger_canteen_liqinbin_prompt()
            return
        if event_id == "canteen_universal_key_prompt":
            self._trigger_canteen_universal_key_prompt()
            return
        if event_id == "store_iron_gate_observation":
            self._trigger_store_iron_gate_observation()
            return
        if event_id == "gym_iron_gate_observation":
            self._trigger_gym_iron_gate_observation()
            return
        if event_id == "battle_escape_blocked_notice":
            self._trigger_battle_escape_blocked_notice()
            return
        raise ValueError(f"unknown scene event id: {event_id}")

    def _apply_game_event_trigger(self, event_id: str) -> None:
        """
        Apply one known backend-defined game event by id.
        """

        if not event_id:
            raise ValueError("game_event.trigger requires a non-empty event id.")
        self._flush_queue_before_event_if_needed(event_id)
        if event_id == "opening_borrow_hotspot_handoff":
            self._trigger_opening_borrow_hotspot_handoff()
            return
        if event_id == "install_update_game_with_own_phone":
            self._trigger_install_update_game(use_ma_phone=False)
            return
        if event_id == "install_update_game_with_ma_phone":
            self._trigger_install_update_game(use_ma_phone=True)
            return
        if event_id == "international_it_teacher_reveal_confiscate":
            self._resolve_international_it_teacher_confiscate()
            return
        if event_id == "destroy_dezheng_blue_device_with_heavy":
            self._trigger_destroy_dezheng_blue_device_with_heavy()
            return
        if event_id == "break_gate_guard_blockade_with_units":
            self._trigger_break_gate_guard_blockade_with_units()
            return
        if event_id == "canteen_liqinbin_remind_and_token":
            self._trigger_canteen_liqinbin_remind_and_token()
            return
        if event_id == "canteen_collect_universal_key":
            self._trigger_canteen_collect_universal_key()
            return
        if event_id == "unlock_store_iron_gate_with_key":
            self._trigger_unlock_store_iron_gate_with_key()
            return
        if event_id == "unlock_gym_iron_gate_with_key":
            self._trigger_unlock_gym_iron_gate_with_key()
            return
        if event_id == "break_store_iron_gate_with_heavy":
            self._trigger_break_store_iron_gate_with_heavy()
            return
        if event_id == "lzb_trigger_dezheng_device_blast":
            self._trigger_lzb_dezheng_device_blast()
            return
        raise ValueError(f"unknown game event id: {event_id}")

    def _flush_queue_before_event_if_needed(self, event_id: str) -> None:
        """
        Some game events evaluate on-field troop power. If deploy commands were queued
        earlier in the same turn, ensure they are materialized before event checks.
        """
        if not self.message_queue:
            return
        need_materialized_units = {
            "break_gate_guard_blockade_with_units",
            "destroy_dezheng_blue_device_with_heavy",
            "break_store_iron_gate_with_heavy",
        }
        if event_id not in need_materialized_units:
            return
        self.flush_queue()

    def _resolve_role_name_alias(self, role_name: str) -> str:
        raw = str(role_name or "").strip()
        if not raw:
            return raw
        lowered = raw.lower()
        if lowered in {"main_player", "mainplayer", "main-player"}:
            return str(self.engine.main_player_name or raw)
        if raw in {"主控", "主角"}:
            return str(self.engine.main_player_name or raw)
        return raw

    def _trigger_install_update_game(self, use_ma_phone: bool) -> None:
        if self.engine.main_player_name is None:
            raise ValueError("global main_player must be set before game_event.trigger.")
        main_name = self.engine.main_player_name
        dynamic_states = set(self.engine.global_config.dynamic_states)
        has_ma_phone = "开场事件:主控已持有马超鹏主手机" in dynamic_states

        if use_ma_phone and not has_ma_phone:
            raise ValueError("cannot install with 马超鹏主手机: main player does not hold it.")
        if (not use_ma_phone) and self.engine.global_config.main_game_state == "confiscated" and (not has_ma_phone):
            raise ValueError("cannot install with own phone while phone is confiscated.")

        # Backend-handled fixed event: downloading/installation consumes 2 time units.
        self.engine.set_main_game_state("downloading")
        self.engine.advance_time(2.0)
        self.engine.set_main_game_state("installed")
        self.engine.set_player_holy_water(main_name, 0.0)
        # card_valid is managed by engine gate (4 by default, 8 if main token is active).
        if use_ma_phone:
            self.engine.add_global_dynamic_state("既定事件:使用马超鹏主手机下载并安装完成")
        else:
            self.engine.add_global_dynamic_state("既定事件:使用当前手机下载安装完成")
        self.engine.global_config.add_global_state(GLOBAL_STATE_GAME_INSTALL_DONE)

    def _trigger_opening_borrow_hotspot_handoff(self) -> None:
        if self.engine.main_player_name is None:
            raise ValueError("global main_player must be set before game_event.trigger.")
        main_name = self.engine.main_player_name
        main_role = self.engine.get_role(main_name)
        if main_role.current_location != "东教学楼内部":
            raise ValueError("opening hotspot handoff event requires main player at 东教学楼内部.")
        now = float(self.engine.global_config.current_time_unit)
        if now >= 5.0:
            raise ValueError("opening hotspot handoff event exceeded time window.")

        states = set(self.engine.global_config.dynamic_states)
        if "开场事件:马超鹏已主动交付主手机" in states:
            return

        ma_profile = self.engine.get_companion_profile("马超鹏")
        self.engine.set_companion_discovered("马超鹏", True)
        self.engine.set_companion_in_team("马超鹏", True)
        self.engine.set_player_card_deck(main_name, list(ma_profile.deck))
        self.engine.set_main_game_state("installed")
        self.engine.set_player_holy_water(main_name, 0.0)
        self.engine.global_config.add_global_state(GLOBAL_STATE_GAME_INSTALL_DONE)

        self.engine.add_global_dynamic_state("开场分支:借马超鹏热点更新")
        self.engine.add_global_dynamic_state("开场事件:主控已持有马超鹏主手机")
        self.engine.add_global_dynamic_state("开场事件:马超鹏已主动交付主手机")
        self.engine.add_global_dynamic_state("手机被老师没收")
        self.engine.add_global_dynamic_state("马超鹏把他的手机给你 与你同行")

        self.engine.advance_time(2.0)

    def _trigger_east_toilet_yanhongfan_encounter(self) -> None:
        marker = "场景事件:厕所遭遇颜宏帆已触发"
        if marker in self.engine.global_config.dynamic_states:
            return
        if self.engine.main_player_name is None:
            raise ValueError("global main_player must be set before scene_event.trigger.")
        main_name = self.engine.main_player_name
        now = float(self.engine.global_config.current_time_unit)
        if now > 5.0:
            raise ValueError("scene event no longer available: time window exceeded.")
        if self.engine.get_role(main_name).current_location != "东教学楼内部":
            raise ValueError("scene event requires main player at 东教学楼内部.")
        if "颜宏帆" not in self.engine.campus_map.roles:
            raise ValueError("scene event target role missing: 颜宏帆")
        if self.engine.get_role("颜宏帆").health <= 0:
            raise ValueError("scene event target role is dead: 颜宏帆")

        self.engine.set_main_player(main_name)
        self.engine.set_battle_state("颜宏帆")
        self.engine.set_role_battle_target(main_name, "颜宏帆")
        self.engine.set_role_battle_target("颜宏帆", main_name)
        self.engine.add_global_dynamic_state(marker)

    def _trigger_opening_phone_choice_window(self) -> None:
        """
        Opening classroom choice reminder event.
        This event only reinforces narrative constraints and does not directly mutate core branch outcome.
        """
        if self.engine.main_player_name is None:
            raise ValueError("global main_player must be set before scene_event.trigger.")
        now = float(self.engine.global_config.current_time_unit)
        if now >= 5.0:
            raise ValueError("scene event no longer available: opening choice window exceeded.")
        main_name = self.engine.main_player_name
        if self.engine.get_role(main_name).current_location != "东教学楼内部":
            raise ValueError("scene event requires main player at 东教学楼内部.")
        self.engine.add_global_dynamic_state("开场事件:手机更新方式抉择已被强调")

    def _trigger_international_it_teacher_encounter(self) -> None:
        if self.engine.main_player_name is None:
            raise ValueError("global main_player must be set before scene_event.trigger.")
        if INTL_TEACHER_EVENT_DONE in self.engine.global_config.dynamic_states:
            return
        if INTL_TEACHER_EVENT_PENDING in self.engine.global_config.dynamic_states:
            return
        if not self._is_character_or_role_alive("信息老师"):
            raise ValueError("scene event unavailable: 信息老师已不在场。")
        main_name = self.engine.main_player_name
        main_role = self.engine.get_role(main_name)
        if main_role.current_location != "国际部":
            raise ValueError("scene event requires main player at 国际部.")
        if not self.engine.campus_map.is_node_valid("国际部"):
            raise ValueError("scene event unavailable: 国际部已被摧毁.")
        if "警报状态" in set(self.engine.global_config.global_states):
            raise ValueError("scene event unavailable: not in normal-time window.")
        self.engine.add_global_dynamic_state(INTL_TEACHER_EVENT_PENDING)

    def _resolve_international_it_teacher_confiscate(self) -> None:
        if self.engine.main_player_name is None:
            raise ValueError("global main_player must be set before game_event.trigger.")
        main_name = self.engine.main_player_name
        main_role = self.engine.get_role(main_name)
        if not self._is_character_or_role_alive("信息老师"):
            raise ValueError("international teacher event unavailable: 信息老师已不在场。")
        if main_role.current_location != "国际部":
            raise ValueError("international teacher event requires main player at 国际部.")
        if not self.engine.campus_map.is_node_valid("国际部"):
            raise ValueError("international teacher event unavailable: 国际部已被摧毁.")
        dynamic_states = set(self.engine.global_config.dynamic_states)
        if INTL_TEACHER_EVENT_DONE in dynamic_states:
            raise ValueError("international teacher event already resolved.")
        if INTL_TEACHER_EVENT_PENDING not in dynamic_states:
            # Allow direct resolve in the same turn as encounter intent.
            self.engine.add_global_dynamic_state(INTL_TEACHER_EVENT_PENDING)

        # Reveal branch: once player gets close enough to recognize the teacher, the teacher intervenes immediately.
        self.engine.global_config.remove_dynamic_state(INTL_TEACHER_EVENT_PENDING)
        self.engine.add_global_dynamic_state(INTL_TEACHER_EVENT_DONE)
        self.engine.add_global_dynamic_state(INTL_TEACHER_EXIT_BLOCKED)

        # Branch A: game already installed -> uninstall only (phone remains with player).
        if str(self.engine.global_config.main_game_state) == "installed":
            self.engine.add_global_dynamic_state(INTL_TEACHER_EVENT_CONFISCATED)
            self.engine.add_global_dynamic_state("信息老师冷声训诫：游戏就是毒品，并当场卸载了你的游戏。")
            self.engine.add_global_dynamic_state("信息老师没有收走手机，你仍持有当前手机。")
            self.engine.set_main_game_state("not_installed")
            self.engine.set_player_holy_water(main_name, 0.0)
            main_player = self.engine.get_player(main_name)
            main_player.active_units.clear()
            main_player.set_card_valid(0)
        else:
            # Branch B: game not installed -> one-round warning dialog only.
            self.engine.add_global_dynamic_state("信息老师进行常规劝导：近期很多学生沉迷手机游戏。")
            self.engine.add_global_dynamic_state("信息老师强调：游戏就是毒品，不要下载。")
            self.engine.add_global_dynamic_state("信息老师站位封锁国际部出口，主控无法从国际部翻出校园。")

        self.engine.advance_time(2.0)

    def _trigger_south_building_chenluo_heal_encounter(self) -> None:
        if self.engine.main_player_name is None:
            raise ValueError("global main_player must be set before scene_event.trigger.")
        if SOUTH_BUILDING_CHENLUO_DONE in self.engine.global_config.dynamic_states:
            return
        main_name = self.engine.main_player_name
        main_role = self.engine.get_role(main_name)
        if main_role.current_location != "南教学楼":
            raise ValueError("scene event requires main player at 南教学楼.")
        if not self.engine.campus_map.is_node_valid("南教学楼"):
            raise ValueError("scene event unavailable: 南教学楼已被摧毁.")
        now = float(self.engine.global_config.current_time_unit)
        if now >= 10.0:
            raise ValueError("scene event no longer available: time window exceeded.")
        if "陈洛" not in self.engine.campus_map.roles:
            raise ValueError("scene event target role missing: 陈洛")
        if self.engine.get_role("陈洛").health <= 0:
            raise ValueError("scene event target role is dead: 陈洛")

        self.engine.set_role_health(main_name, self.engine.get_role(main_name).health + 3.0)
        self.engine.add_global_dynamic_state(SOUTH_BUILDING_CHENLUO_DONE)
        self.engine.add_global_dynamic_state("陈洛用手机施放治疗法术，主控生命+3后离开。")
        if "陈洛" in self.engine.character_profiles:
            self.engine.set_character_status("陈洛", "离开校园")
        if "陈洛" in self.engine.campus_map.roles:
            role = self.engine.get_role("陈洛")
            self.engine.campus_map.get_node(role.current_location).remove_role("陈洛")
            del self.engine.campus_map.roles["陈洛"]

    def _trigger_dezheng_blue_device_observation(self) -> None:
        if self.engine.main_player_name is None:
            raise ValueError("global main_player must be set before scene_event.trigger.")
        if DEZHENG_BLUE_DEVICE_SEEN in self.engine.global_config.dynamic_states:
            return
        if DEZHENG_BLUE_DEVICE_DESTROYED in self.engine.global_config.dynamic_states:
            return
        main_name = self.engine.main_player_name
        main_role = self.engine.get_role(main_name)
        if main_role.current_location != "德政楼":
            raise ValueError("scene event requires main player at 德政楼.")
        if not self.engine.campus_map.is_node_valid("德政楼"):
            raise ValueError("scene event unavailable: 德政楼已坍塌。")
        self.engine.add_global_dynamic_state(DEZHENG_BLUE_DEVICE_SEEN)
        self.engine.add_global_dynamic_state("你看见奇怪装置发出笼罩全校的蓝光。")

    def _trigger_destroy_dezheng_blue_device_with_heavy(self) -> None:
        if self.engine.main_player_name is None:
            raise ValueError("global main_player must be set before game_event.trigger.")
        main_name = self.engine.main_player_name
        main_role = self.engine.get_role(main_name)
        if main_role.current_location != "德政楼":
            raise ValueError("game event requires main player at 德政楼.")
        if not self.engine.campus_map.is_node_valid("德政楼"):
            raise ValueError("game event unavailable: 德政楼已坍塌。")
        states = set(self.engine.global_config.dynamic_states)
        if DEZHENG_BLUE_DEVICE_DESTROYED in states:
            raise ValueError("device is already destroyed.")
        if DEZHENG_BLUE_DEVICE_SEEN not in states:
            raise ValueError("device is not discovered yet.")
        if not self._has_heavy_strike_at_node(main_name, "德政楼"):
            raise ValueError(
                "cannot destroy device: no heavy strike source at 德政楼 "
                f"(need attack>={DEZHENG_HEAVY_MIN_ATTACK:g} or consume>={DEZHENG_HEAVY_MIN_CONSUME:g})."
            )

        self.engine.add_global_dynamic_state(DEZHENG_BLUE_DEVICE_DESTROYED)
        self.engine.add_global_dynamic_state("重型打击击毁蓝光装置，德政楼随之坍塌。")
        self.engine.event_checker.collapse_structure_now("德政楼", reason="main_player_destroyed_blue_device")
        # This action itself consumes one round.
        self.engine.advance_time(2.0)

    def _has_heavy_strike_at_node(self, main_name: str, node_name: str) -> bool:
        player = self.engine.get_player(main_name)
        for unit in player.list_active_units():
            if unit.node_name != node_name:
                continue
            if (
                float(unit.card.attack) >= DEZHENG_HEAVY_MIN_ATTACK
                or float(unit.card.consume) >= DEZHENG_HEAVY_MIN_CONSUME
            ):
                return True
        return False

    def _collect_heavy_strike_sources_at_node(self, main_name: str, node_name: str) -> list[str]:
        player = self.engine.get_player(main_name)
        rows: list[str] = []
        for unit in player.list_active_units():
            if unit.node_name != node_name:
                continue
            if (
                float(unit.card.attack) < DEZHENG_HEAVY_MIN_ATTACK
                and float(unit.card.consume) < DEZHENG_HEAVY_MIN_CONSUME
            ):
                continue
            rows.append(f"{unit.owner_name}:{unit.card.name}")
        return sorted(rows)

    def _trigger_gate_guard_blockade_observation(self) -> None:
        if self.engine.main_player_name is None:
            raise ValueError("global main_player must be set before scene_event.trigger.")
        main_name = self.engine.main_player_name
        node_name = self.engine.get_role(main_name).current_location
        seen_marker, broken_marker = self._gate_guard_markers(node_name)
        if not seen_marker or not broken_marker:
            raise ValueError("scene event requires main player at 正门 or 后门.")
        if broken_marker in self.engine.global_config.dynamic_states:
            return
        if seen_marker in self.engine.global_config.dynamic_states:
            return
        self.engine.add_global_dynamic_state(seen_marker)
        self.engine.add_global_dynamic_state(
            f"{node_name}保安神情死板地挡在出口前，任何口头劝说都无效。"
        )

    def _trigger_break_gate_guard_blockade_with_units(self) -> None:
        if self.engine.main_player_name is None:
            raise ValueError("global main_player must be set before game_event.trigger.")
        main_name = self.engine.main_player_name
        node_name = self.engine.get_role(main_name).current_location
        seen_marker, broken_marker = self._gate_guard_markers(node_name)
        if not seen_marker or not broken_marker:
            raise ValueError("game event requires main player at 正门 or 后门.")
        states = set(self.engine.global_config.dynamic_states)
        if broken_marker in states:
            raise ValueError("gate guard blockade is already broken.")

        total_power, sources = self._collect_gate_guard_break_power(main_name, node_name)
        if total_power + 1e-9 < GATE_GUARD_BREAK_MIN_POWER:
            raise ValueError(
                "cannot break guard blockade: insufficient troop power "
                f"(need>={GATE_GUARD_BREAK_MIN_POWER:g}, current={total_power:g})."
            )

        if seen_marker not in states:
            self.engine.add_global_dynamic_state(seen_marker)
        self.engine.add_global_dynamic_state(broken_marker)
        self.engine.add_global_dynamic_state(
            f"{node_name}保安防线被部队强行冲破，出口暂时打通。"
        )
        if sources:
            self.engine.add_global_dynamic_state(
                f"{node_name}突破参与单位：{', '.join(sources)}"
            )
        self.engine.advance_time(1.0)

    def _trigger_canteen_liqinbin_prompt(self) -> None:
        if self.engine.main_player_name is None:
            raise ValueError("global main_player must be set before scene_event.trigger.")
        if CANTEEN_LIQINBIN_DONE in self.engine.global_config.dynamic_states:
            return
        if CANTEEN_LIQINBIN_PENDING in self.engine.global_config.dynamic_states:
            return
        if not self._is_character_or_role_alive("李秦彬"):
            raise ValueError("scene event unavailable: 李秦彬已不在场。")
        main_name = self.engine.main_player_name
        main_role = self.engine.get_role(main_name)
        if main_role.current_location != "食堂":
            raise ValueError("scene event requires main player at 食堂.")
        if not self.engine.campus_map.is_node_valid("食堂"):
            raise ValueError("scene event unavailable: 食堂已被摧毁。")
        self.engine.add_global_dynamic_state(CANTEEN_LIQINBIN_PENDING)
        self.engine.add_global_dynamic_state("你看见李秦彬低头吃饭，似乎还不知道校园里发生了什么。")

    def _trigger_canteen_liqinbin_remind_and_token(self) -> None:
        if self.engine.main_player_name is None:
            raise ValueError("global main_player must be set before game_event.trigger.")
        main_name = self.engine.main_player_name
        main_role = self.engine.get_role(main_name)
        if main_role.current_location != "食堂":
            raise ValueError("game event requires main player at 食堂.")
        if not self.engine.campus_map.is_node_valid("食堂"):
            raise ValueError("game event unavailable: 食堂已被摧毁。")
        if not self._is_character_or_role_alive("李秦彬"):
            raise ValueError("game event unavailable: 李秦彬已不在场。")
        states = set(self.engine.global_config.dynamic_states)
        if CANTEEN_LIQINBIN_DONE in states:
            raise ValueError("canteen liqinbin event already resolved.")
        if CANTEEN_LIQINBIN_PENDING not in states:
            self.engine.add_global_dynamic_state(CANTEEN_LIQINBIN_PENDING)

        self.engine.advance_time(1.5)
        self.engine.global_config.remove_dynamic_state(CANTEEN_LIQINBIN_PENDING)
        self.engine.add_global_dynamic_state(CANTEEN_LIQINBIN_DONE)
        self.engine.add_global_dynamic_state("你提醒了李秦彬校园异变，他明显很感激你。")
        self.engine.add_global_dynamic_state("李秦彬给主控手机充值了一个皇室令牌。")
        self.engine.add_global_dynamic_state(MAIN_ROYALE_TOKEN_ACTIVE)
        self.engine.add_global_dynamic_state(MAIN_ROYALE_TOKEN_FLAG)

        # Token effect applies to main player's own phone only.
        self.engine.get_player(main_name).set_card_valid(8)

    def _trigger_canteen_universal_key_prompt(self) -> None:
        if self.engine.main_player_name is None:
            raise ValueError("global main_player must be set before scene_event.trigger.")
        states = set(self.engine.global_config.dynamic_states)
        if CANTEEN_UNIVERSAL_KEY_COLLECTED in states:
            return
        if CANTEEN_UNIVERSAL_KEY_PENDING in states:
            return
        main_name = self.engine.main_player_name
        main_role = self.engine.get_role(main_name)
        if main_role.current_location != "食堂":
            raise ValueError("scene event requires main player at 食堂.")
        if not self.engine.campus_map.is_node_valid("食堂"):
            raise ValueError("scene event unavailable: 食堂已被摧毁。")
        self.engine.add_global_dynamic_state(CANTEEN_UNIVERSAL_KEY_PENDING)
        self.engine.add_global_dynamic_state("你在食堂角落发现一把挂着旧标签的万能钥匙。")

    def _trigger_store_iron_gate_observation(self) -> None:
        if self.engine.main_player_name is None:
            raise ValueError("global main_player must be set before scene_event.trigger.")
        states = set(self.engine.global_config.dynamic_states)
        if STORE_GATE_OPENED in states or STORE_GATE_BROKEN in states:
            return
        if STORE_GATE_SEEN in states:
            return
        main_name = self.engine.main_player_name
        main_role = self.engine.get_role(main_name)
        if main_role.current_location != "小卖部":
            raise ValueError("scene event requires main player at 小卖部.")
        if not self.engine.campus_map.is_node_valid("小卖部"):
            raise ValueError("scene event unavailable: 小卖部已被摧毁。")
        self.engine.add_global_dynamic_state(STORE_GATE_SEEN)
        self.engine.add_global_dynamic_state("小卖部铁门紧闭，门缝里只透出凌乱的货架影子。")

    def _trigger_gym_iron_gate_observation(self) -> None:
        if self.engine.main_player_name is None:
            raise ValueError("global main_player must be set before scene_event.trigger.")
        states = set(self.engine.global_config.dynamic_states)
        if GYM_GATE_OPENED in states:
            return
        if GYM_GATE_SEEN in states:
            return
        main_name = self.engine.main_player_name
        main_role = self.engine.get_role(main_name)
        if main_role.current_location != "体育馆":
            raise ValueError("scene event requires main player at 体育馆.")
        if not self.engine.campus_map.is_node_valid("体育馆"):
            raise ValueError("scene event unavailable: 体育馆已被摧毁。")
        self.engine.add_global_dynamic_state(GYM_GATE_SEEN)
        self.engine.add_global_dynamic_state("体育馆铁门卡死，门锁像被某种力量焊住。")

    def _trigger_battle_escape_blocked_notice(self) -> None:
        if self.engine.main_player_name is None:
            raise ValueError("global main_player must be set before scene_event.trigger.")
        main_name = self.engine.main_player_name
        main_role = self.engine.get_role(main_name)
        if main_role.current_location not in {"正门", "后门", "国际部"}:
            raise ValueError("scene event requires main player at escape-edge node.")
        if self.engine.global_config.battle_state is None:
            raise ValueError("scene event requires active battle state.")
        self.engine.add_global_dynamic_state("注意：玩家正在交战，试图从门口逃离会被拦下。")

    def _trigger_canteen_collect_universal_key(self) -> None:
        if self.engine.main_player_name is None:
            raise ValueError("global main_player must be set before game_event.trigger.")
        main_name = self.engine.main_player_name
        main_role = self.engine.get_role(main_name)
        if main_role.current_location != "食堂":
            raise ValueError("game event requires main player at 食堂.")
        if not self.engine.campus_map.is_node_valid("食堂"):
            raise ValueError("game event unavailable: 食堂已被摧毁。")
        states = set(self.engine.global_config.dynamic_states)
        if CANTEEN_UNIVERSAL_KEY_COLLECTED in states:
            raise ValueError("universal key already collected.")
        if CANTEEN_UNIVERSAL_KEY_PENDING not in states:
            self.engine.add_global_dynamic_state(CANTEEN_UNIVERSAL_KEY_PENDING)

        self.engine.advance_time(1.0)
        self.engine.global_config.remove_dynamic_state(CANTEEN_UNIVERSAL_KEY_PENDING)
        self.engine.add_global_dynamic_state(CANTEEN_UNIVERSAL_KEY_COLLECTED)
        self.engine.add_global_dynamic_state("你花了1时间单位在食堂收起万能钥匙，钥匙可用于开启铁门。")
        self.engine.global_config.add_global_state(GLOBAL_STATE_UNIVERSAL_KEY_OWNED)

    def _trigger_unlock_store_iron_gate_with_key(self) -> None:
        if self.engine.main_player_name is None:
            raise ValueError("global main_player must be set before game_event.trigger.")
        main_name = self.engine.main_player_name
        main_role = self.engine.get_role(main_name)
        if main_role.current_location != "小卖部":
            raise ValueError("game event requires main player at 小卖部.")
        if not self.engine.campus_map.is_node_valid("小卖部"):
            raise ValueError("game event unavailable: 小卖部已被摧毁。")
        states = set(self.engine.global_config.dynamic_states)
        if CANTEEN_UNIVERSAL_KEY_COLLECTED not in states:
            raise ValueError("cannot unlock store gate: universal key is not collected.")
        if STORE_GATE_OPENED in states or STORE_GATE_BROKEN in states:
            raise ValueError("store gate is already opened.")

        self.engine.advance_time(1.0)
        self.engine.add_global_dynamic_state(STORE_GATE_OPENED)
        self.engine.add_global_dynamic_state(
            "你用万能钥匙打开了小卖部铁门，里面的魔法零食让你迅速恢复状态。"
        )
        self.engine.set_role_health(main_name, 10.0)
        self.engine.add_global_dynamic_state(MAIN_MAGIC_SNACK_BUFF_ACTIVE)
        self.engine.add_global_dynamic_state(
            "状态变更：主控与同行可攻击友方角色（许琪琪除外）拳头强化为2点魔法小范围AOE。"
        )
        self.engine.global_config.add_global_state(GLOBAL_STATE_MAGIC_SNACK_BUFF)

    def _trigger_unlock_gym_iron_gate_with_key(self) -> None:
        if self.engine.main_player_name is None:
            raise ValueError("global main_player must be set before game_event.trigger.")
        main_name = self.engine.main_player_name
        main_role = self.engine.get_role(main_name)
        if main_role.current_location != "体育馆":
            raise ValueError("game event requires main player at 体育馆.")
        if not self.engine.campus_map.is_node_valid("体育馆"):
            raise ValueError("game event unavailable: 体育馆已被摧毁。")
        states = set(self.engine.global_config.dynamic_states)
        if CANTEEN_UNIVERSAL_KEY_COLLECTED not in states:
            raise ValueError("cannot unlock gym gate: universal key is not collected.")
        if GYM_GATE_OPENED in states:
            raise ValueError("gym gate is already opened.")

        self.engine.advance_time(1.0)
        self.engine.add_global_dynamic_state(GYM_GATE_OPENED)
        self.engine.add_global_dynamic_state("你用万能钥匙打开了体育馆铁门。")
        if DYNAMIC_GYM_INTERLUDE_DONE not in set(self.engine.global_config.dynamic_states):
            self.engine.add_global_dynamic_state(DYNAMIC_GYM_INTERLUDE_DONE)
            self.engine.add_global_dynamic_state("体育馆宣传片播到校歌间奏，众人短暂沉睡后惊醒。")
            self.engine.add_global_dynamic_state("时流错位：体感像是回到更早时刻，但其他角色状态未倒退。")
            self._apply_time_rewind_for_gym_interlude(4.0)

    def _trigger_lzb_dezheng_device_blast(self) -> None:
        if not self.engine.enemy_director.resolve_lzb_dezheng_pending():
            raise ValueError("cannot resolve lzb dezheng blast: no pending event or already canceled.")

    def _apply_time_rewind_for_gym_interlude(self, amount: float) -> None:
        rewind = float(amount)
        if rewind <= 0:
            return
        current = float(self.engine.global_config.current_time_unit)
        next_time = max(0.0, current - rewind)
        shifted = current - next_time
        if shifted <= 1e-9:
            return
        # Only rewind global timeline and delay scripted triggers.
        # Role positions / health / enemy runtime counters are intentionally unchanged.
        self.engine.global_config.current_time_unit = next_time
        self.engine.global_config.shift_untriggered_trigger_times(shifted)
        self.engine.global_config.add_dynamic_state(
            f"体育馆时流回卷：时间- {shifted:g}，未触发trigger整体顺延+{shifted:g}。"
        )

    def _trigger_break_store_iron_gate_with_heavy(self) -> None:
        if self.engine.main_player_name is None:
            raise ValueError("global main_player must be set before game_event.trigger.")
        main_name = self.engine.main_player_name
        main_role = self.engine.get_role(main_name)
        if main_role.current_location != "小卖部":
            raise ValueError("game event requires main player at 小卖部.")
        if not self.engine.campus_map.is_node_valid("小卖部"):
            raise ValueError("game event unavailable: 小卖部已被摧毁。")
        states = set(self.engine.global_config.dynamic_states)
        if STORE_GATE_OPENED in states or STORE_GATE_BROKEN in states:
            raise ValueError("store gate is already opened.")
        if not self._has_heavy_strike_at_node(main_name, "小卖部"):
            raise ValueError(
                "cannot break store gate: no heavy strike source at 小卖部 "
                f"(need attack>={DEZHENG_HEAVY_MIN_ATTACK:g} or consume>={DEZHENG_HEAVY_MIN_CONSUME:g})."
            )

        self.engine.advance_time(2.0)
        self.engine.add_global_dynamic_state(STORE_GATE_OPENED)
        self.engine.add_global_dynamic_state(STORE_GATE_BROKEN)
        self.engine.add_global_dynamic_state(STORE_INSIDE_MESS)
        self.engine.add_global_dynamic_state("你强行击破了小卖部铁门，里面已经乱成一团糟。")
        sources = self._collect_heavy_strike_sources_at_node(main_name, "小卖部")
        if sources:
            self.engine.add_global_dynamic_state(f"小卖部破门参与重型单位：{', '.join(sources)}")

    @staticmethod
    def _gate_guard_markers(node_name: str) -> tuple[str | None, str | None]:
        if node_name == "正门":
            return GATE_GUARD_SEEN_FRONT, GATE_GUARD_BROKEN_FRONT
        if node_name == "后门":
            return GATE_GUARD_SEEN_BACK, GATE_GUARD_BROKEN_BACK
        return None, None

    def _collect_gate_guard_break_power(self, main_name: str, node_name: str) -> tuple[float, list[str]]:
        player = self.engine.get_player(main_name)
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

    def _is_character_or_role_alive(self, role_name: str) -> bool:
        exists = False
        if role_name in self.engine.character_profiles:
            exists = True
            if self.engine.get_character_profile(role_name).status != "存活":
                return False
        if role_name in self.engine.campus_map.roles:
            exists = True
            if self.engine.get_role(role_name).health <= 0:
                return False
        return exists

    @staticmethod
    def _parse_deploy_payload(text: str) -> tuple[str, str | None]:
        if "@" in text:
            card_name, node_name = text.split("@", 1)
            return card_name.strip(), node_name.strip()
        return text.strip(), None

    @staticmethod
    def _parse_nearby_units(text: str) -> dict[str, str]:
        if not text:
            return {}
        items: dict[str, str] = {}
        for part in text.split(","):
            raw = part.strip()
            if not raw:
                continue
            if ":" not in raw:
                raise ValueError("nearby_units must use name:status pairs.")
            unit_name, status = raw.split(":", 1)
            items[unit_name.strip()] = CommandPipeline._normalize_nearby_status(status.strip())
        return items

    @staticmethod
    def _parse_nearby_unit_names(text: str) -> list[str]:
        rows: list[str] = []
        for part in str(text or "").split(","):
            raw = part.strip()
            if not raw:
                continue
            if ":" in raw:
                name = raw.split(":", 1)[0].strip()
            else:
                name = raw
            if name:
                rows.append(name)
        return rows

    @staticmethod
    def _normalize_nearby_status(status: str) -> str:
        raw = str(status or "").strip()
        lowered = raw.lower()
        if lowered in {"full", "alive", "healthy"} or raw in {"存活", "完整", "满血", "健康"}:
            return "full"
        if lowered in {"damaged", "injured", "wounded"} or raw in {"受伤", "残血", "受损"}:
            return "damaged"
        if lowered in {"dead", "down", "destroyed"} or raw in {"死亡", "击杀", "被击杀", "阵亡", "摧毁"}:
            return "dead"
        raise ValueError(
            "nearby unit status must be full/damaged/dead (or 存活/受伤/死亡 synonyms)."
        )

    def _get_named_nearby_unit_health(self, role_name: str, unit_name: str) -> float | None:
        if role_name not in self.engine.players:
            return None
        role = self.engine.get_role(role_name)
        player = self.engine.get_player(role_name)
        candidates = [u for u in player.list_active_units() if u.card.name == unit_name]
        if not candidates:
            return None
        local = [u for u in candidates if u.node_name == role.current_location]
        pool = local if local else candidates
        pool.sort(key=lambda u: (float(u.current_health), float(u.deployed_time)))
        return float(pool[0].current_health)

    def _set_named_nearby_unit_health(self, role_name: str, unit_name: str, value: float) -> None:
        role = self.engine.get_role(role_name)
        if role_name in self.engine.players:
            player = self.engine.get_player(role_name)
            candidates = [u for u in player.list_active_units() if u.card.name == unit_name]
            local = [u for u in candidates if u.node_name == role.current_location]
            pool = local if local else candidates
            if pool:
                pool.sort(key=lambda u: (float(u.current_health), float(u.deployed_time)))
                target = pool[0]
                if value <= 0:
                    player.remove_unit(target.unit_id)
                    role.set_nearby_unit_status(unit_name, "dead")
                    return
                target.current_health = float(value)
                max_hp = float(target.card.health)
                role.set_nearby_unit_status(unit_name, "damaged" if value < max_hp else "full")
                return
        # Fallback for purely narrative nearby_unit entries without runtime unit id.
        if value <= 0:
            role.set_nearby_unit_status(unit_name, "dead")
        elif value < 1:
            role.set_nearby_unit_status(unit_name, "damaged")
        else:
            role.set_nearby_unit_status(unit_name, "full")

    @staticmethod
    def _normalize_bracket_command(line: str) -> str:
        normalized = line.strip()
        lowered = normalized.lower()
        if lowered in ("[command]", "[/command]"):
            return normalized
        if normalized.startswith("[") and normalized.endswith("]"):
            inner = normalized[1:-1].strip()
            if inner:
                return inner
        return normalized
