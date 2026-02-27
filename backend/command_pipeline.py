"""
Module purpose:
- Compile simple string commands into game operations and queue messages.

Core design:
- `move` and `deploy` commands are queued in `message_queue`.
- Most state updates are applied immediately when compiling.
- `queue.flush=true` executes queued messages in order.

Supported syntax summary:
- Comment/blank: lines starting with `#` or empty lines are ignored.
- Assignment: `left=right`
- Append/remove text: `left+=text`, `left-=text` for `global.state` / `<role>.state`
- Numeric delta: `left+=number`, `left-=number` for numeric fields

Queue commands:
- `<role>.move=<node>`
- `<role>.deploy=<card_name>`
- `<role>.deploy=<card_name>@<node>`
- `queue.flush=true`
- `queue.clear=true`

Immediate state commands:
- `time.advance=<number>` (must be multiple of 0.5)
- `global.battle=<true|false>`
- `global.emergency=<true|false>`
- `<role>.location=<node>`
- `<role>.health=<number>`
- `<role>.holy_water=<number>`
- `<role>.card_valid=<int>`
- `<role>.nearby_units=<unitA:full,unitB:damaged>`
- `<role>.nearby_unit.<unit_name>=<full|damaged|dead>`
- `<role>.unit.<unit_id>.health=<number>` (<=0 means dead, remove from active list)

Dynamic text commands:
- `global.state+=<text>`
- `global.state-=<text>`
- `<role>.state+=<text>`
- `<role>.state-=<text>`
"""

from __future__ import annotations

from dataclasses import dataclass

from .engine import GameEngine
from .roles import PlayerRole


@dataclass
class QueueMessage:
    """One queued action to be executed later."""

    action: str
    role_name: str
    payload: dict[str, str]
    source_line: str


class CommandPipeline:
    """Compile command text and drive queue/state operations."""

    def __init__(self, engine: GameEngine) -> None:
        self.engine = engine
        self.message_queue: list[QueueMessage] = []
        self.runtime_messages: list[str] = []

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

        if "+=" in line:
            left, right = line.split("+=", 1)
            self._apply_plus(left.strip(), right.strip())
            return
        if "-=" in line:
            left, right = line.split("-=", 1)
            self._apply_minus(left.strip(), right.strip())
            return
        if "=" in line:
            left, right = line.split("=", 1)
            self._apply_assign(left.strip(), right.strip(), line)
            return
        raise ValueError(f"invalid command syntax: {line}")

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
            elif msg.action == "deploy":
                player = self.engine.get_player(msg.role_name)
                card_name = msg.payload.get("card_name")
                node_name = msg.payload.get("node_name")
                player.deploy_from_deck(card_name=card_name, node_name=node_name)
                self.runtime_messages.append(
                    f"queued deploy executed: {msg.role_name} card={card_name or 'TOP'}"
                )
            else:
                raise ValueError(f"unknown queue action: {msg.action}")
            executed += 1
        self.runtime_messages.append(f"queue flushed: {executed} message(s)")
        return list(self.runtime_messages)

    def _apply_plus(self, left: str, right: str) -> None:
        if left == "global.state":
            self.engine.add_global_dynamic_state(right)
            self.runtime_messages.append("global dynamic state appended")
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
            self.engine.set_battle_phase(self._parse_bool(right))
            self.runtime_messages.append(f"global battle set: {right}")
            return
        if left == "global.emergency":
            self.engine.set_emergency_phase(self._parse_bool(right))
            self.runtime_messages.append(f"global emergency set: {right}")
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
        if field == "health":
            self.engine.set_role_health(role_name, self._parse_float(right))
            self.runtime_messages.append(f"health set: {role_name}")
            return
        if field == "holy_water":
            self.engine.set_player_holy_water(role_name, self._parse_float(right))
            self.runtime_messages.append(f"holy_water set: {role_name}")
            return
        if field == "card_valid":
            player = self.engine.get_player(role_name)
            player.set_card_valid(int(right))
            self.runtime_messages.append(f"card_valid set: {role_name} -> {right}")
            return
        if field == "nearby_units":
            role.replace_nearby_units(self._parse_nearby_units(right))
            self.runtime_messages.append(f"nearby_units replaced: {role_name}")
            return
        if field == "nearby_unit" and len(left_parts) >= 3:
            unit_name = ".".join(left_parts[2:])
            role.set_nearby_unit_status(unit_name, right)
            self.runtime_messages.append(f"nearby_unit status set: {role_name}.{unit_name}={right}")
            return
        if field == "unit" and len(left_parts) == 4 and left_parts[3] == "health":
            unit_id = left_parts[2]
            self._set_runtime_unit_health(role_name, unit_id, self._parse_float(right))
            self.runtime_messages.append(f"runtime unit health set: {role_name}.{unit_id}")
            return
        raise ValueError(f"unsupported assignment command: {left}={right}")

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
