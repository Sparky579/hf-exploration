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
- `global.battle=<target_role_name|none|true|false>`
- `global.emergency=<true|false>`
- `global.main_player=<player_name>`
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
- `<role>.nearby_units=<unitA:full,unitB:damaged>`
- `<role>.nearby_unit.<unit_name>=<full|damaged|dead>`
- `<role>.unit.<unit_id>.health=<number>` (<=0 means dead, remove from active list)
- `trigger.add=<trigger sentence>`
- `trigger.remove=<id_or_text>`
- `trigger.clear=true`
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

from .engine import GameEngine


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
        if left == "global.team":
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
            role_name = left[:-6]
            self.engine.add_role_dynamic_state(role_name, right)
            self.runtime_messages.append(f"role dynamic state appended: {role_name}")
            return
        self._apply_numeric_delta(left, right, sign=1.0)

    def _apply_minus(self, left: str, right: str) -> None:
        if left == "global.state":
            self.engine.global_config.remove_dynamic_state(right)
            self.runtime_messages.append("global dynamic state removed")
            return
        if left == "global.team":
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
            role_name = left[:-6]
            role = self.engine.get_role(role_name)
            role.remove_dynamic_state(right)
            self.runtime_messages.append(f"role dynamic state removed: {role_name}")
            return
        self._apply_numeric_delta(left, right, sign=-1.0)

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
        if left == "global.team":
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
        role_name = left_parts[0]
        field = left_parts[1]
        role = self.engine.get_role(role_name)

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
        if field == "nearby_units":
            self._assert_role_location_valid_for_internal_action(role_name, "nearby_units")
            role.replace_nearby_units(self._parse_nearby_units(right))
            self.runtime_messages.append(f"nearby_units replaced: {role_name}")
            return
        if field == "nearby_unit" and len(left_parts) >= 3:
            self._assert_role_location_valid_for_internal_action(role_name, "nearby_unit")
            unit_name = ".".join(left_parts[2:])
            role.set_nearby_unit_status(unit_name, right)
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
            self.runtime_messages.append(f"character status set: {name} -> {right}")
            return
        if field == "deck":
            deck = [x.strip() for x in right.split(",") if x.strip()]
            self.engine.set_character_deck(name, deck)
            self.runtime_messages.append(f"character deck set: {name}")
            return
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
        role_name = left_parts[0]
        field = left_parts[1]
        role = self.engine.get_role(role_name)

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
            return "__BATTLE__"
        return text.strip()

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
            items[unit_name.strip()] = status.strip()
        return items

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
