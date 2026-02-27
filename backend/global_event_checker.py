"""
Module purpose:
- Check story triggers whenever time advances and apply global state changes.

Built-in events:
- alert: triggered when `current_time > alert_trigger_time`.
- emergency: triggered after 德政楼 is destroyed and time check runs.
- explosion: triggered when `current_time > emergency_start + emergency_blast_delay`.

Scripted events:
- Trigger sentence fires when `current_time > trigger_time`.
- Supported auto result keywords:
  - `提示:<text>` / `预警:<text>` -> append global dynamic state.
  - `建筑倒塌:<name>` -> destroy mapped node(s), kill all roles at affected nodes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .story_settings import GlobalStorySetting

if TYPE_CHECKING:
    from .engine import GameEngine


@dataclass
class TriggerState:
    alert_triggered: bool = False
    emergency_triggered: bool = False
    explosion_triggered: bool = False
    emergency_start_time: float | None = None
    explosion_time: float | None = None
    escaped_roles: set[str] = field(default_factory=set)
    trigger_history: list[str] = field(default_factory=list)


class GlobalEventChecker:
    """Run story trigger checks and escape validations."""

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

    def __init__(self, engine: GameEngine, story_setting: GlobalStorySetting) -> None:
        self.engine = engine
        self.story_setting = story_setting
        self.state = TriggerState()

    def check_time_triggers(self) -> None:
        """Check all trigger conditions based on current world time and map state."""

        now = self.engine.global_config.current_time_unit
        if (not self.state.alert_triggered) and now > self.story_setting.alert_trigger_time:
            self.state.alert_triggered = True
            self.engine.global_config.add_global_state("警报状态")
            self.engine.global_config.add_dynamic_state("触发：学校进入警报状态")
            self.state.trigger_history.append(f"t={now}: 警报状态触发")

        if (not self.state.emergency_triggered) and (not self.engine.campus_map.is_node_valid("德政楼")):
            self.state.emergency_triggered = True
            self.state.emergency_start_time = now
            self.state.explosion_time = now + self.story_setting.emergency_blast_delay
            self.engine.set_emergency_phase(True)
            self.engine.global_config.add_dynamic_state("触发：德政楼被摧毁，进入紧急状态")
            self.state.trigger_history.append(f"t={now}: 紧急状态触发，爆炸倒计时开始")

        if (
            self.state.emergency_triggered
            and (not self.state.explosion_triggered)
            and self.state.explosion_time is not None
            and now > self.state.explosion_time
        ):
            self.state.explosion_triggered = True
            self.engine.global_config.add_global_state("学校爆炸")
            self.engine.global_config.add_dynamic_state("触发：学校爆炸")
            self.state.trigger_history.append(f"t={now}: 学校爆炸触发")
            for role_name in list(self.engine.campus_map.roles.keys()):
                if role_name in self.state.escaped_roles:
                    continue
                self.engine.set_role_health(role_name, 0)
                self._mark_character_dead_if_exists(role_name)

        self._check_scripted_triggers(now)

    def is_triggered(self, event_name: str) -> bool:
        mapping = {
            "alert": self.state.alert_triggered,
            "emergency": self.state.emergency_triggered,
            "explosion": self.state.explosion_triggered,
        }
        if event_name not in mapping:
            raise KeyError(f"unknown event name: {event_name}")
        return mapping[event_name]

    def can_escape_from(self, node_name: str) -> bool:
        if self.state.explosion_triggered:
            return False

        now = self.engine.global_config.current_time_unit
        if self.state.emergency_triggered and self.state.explosion_time is not None and now <= self.state.explosion_time:
            allowed_nodes = self.story_setting.escape_nodes_during_emergency
        elif not self.state.alert_triggered:
            allowed_nodes = self.story_setting.escape_nodes_before_alert
        else:
            allowed_nodes = set()

        if node_name not in allowed_nodes:
            return False
        if not self.engine.campus_map.is_node_valid(node_name):
            return False
        if node_name == "国际部" and not self.engine.campus_map.is_node_valid("国际部"):
            return False
        return True

    def attempt_escape(self, role_name: str, node_name: str) -> None:
        role = self.engine.get_role(role_name)
        if role.current_location != node_name:
            raise ValueError(f"escape requires role at node: role={role_name}, node={node_name}")
        if not self.can_escape_from(node_name):
            raise ValueError(f"escape is not allowed from node now: {node_name}")
        self.state.escaped_roles.add(role_name)
        role.add_dynamic_state(f"已通过{node_name}逃离校园")
        self.state.trigger_history.append(
            f"t={self.engine.global_config.current_time_unit}: {role_name} 通过{node_name}逃离"
        )

    def recent_trigger_history(self, limit: int = 15) -> list[str]:
        if limit <= 0:
            return []
        return self.state.trigger_history[-limit:]

    def _check_scripted_triggers(self, now: float) -> None:
        for item in self.engine.global_config.scripted_triggers:
            if bool(item["triggered"]):
                continue
            trigger_time = float(item["trigger_time"])
            if now <= trigger_time:
                continue
            item["triggered"] = True
            text = str(item["text"])
            self.engine.global_config.add_dynamic_state(f"脚本触发#{item['id']}: {text}")
            self.state.trigger_history.append(f"t={now}: 脚本触发#{item['id']} -> {text}")
            self._apply_scripted_result(item, now)

    def _apply_scripted_result(self, item: dict[str, object], now: float) -> None:
        result = str(item.get("result", "")).strip()
        if not result:
            return

        if result.startswith("提示:") or result.startswith("预警:"):
            message = result.split(":", 1)[1].strip()
            if message:
                self.engine.global_config.add_dynamic_state(message)
                self.state.trigger_history.append(f"t={now}: 提示 -> {message}")
            return

        marker = "建筑倒塌:"
        if marker in result:
            target = result.split(marker, 1)[1].strip()
            if target:
                self._apply_structure_collapse(target, now)
            return

    def _apply_structure_collapse(self, target: str, now: float) -> None:
        affected_nodes = self._resolve_collapse_nodes(target)
        affected_roles: set[str] = set()
        for node_name in affected_nodes:
            if node_name not in self.engine.campus_map.nodes:
                continue
            node = self.engine.campus_map.get_node(node_name)
            affected_roles.update(node.roles)
            self.engine.set_node_valid(node_name, False)

        for role_name in sorted(affected_roles):
            self.engine.set_role_health(role_name, 0)
            self._mark_character_dead_if_exists(role_name)

        if affected_nodes:
            joined_nodes = ",".join(affected_nodes)
            self.engine.global_config.add_dynamic_state(f"{target}坍塌，影响区域：{joined_nodes}")
            self.state.trigger_history.append(f"t={now}: 建筑倒塌 -> {target} ({joined_nodes})")

    def _resolve_collapse_nodes(self, target: str) -> list[str]:
        if target in self.BUILDING_NODE_MAP:
            return list(self.BUILDING_NODE_MAP[target])
        if target in self.engine.campus_map.nodes:
            return [target]

        hits = [name for name in self.engine.campus_map.nodes if target in name]
        return sorted(hits)

    def _mark_character_dead_if_exists(self, role_name: str) -> None:
        if role_name not in self.engine.character_profiles:
            return
        profile = self.engine.character_profiles[role_name]
        if profile.status != "死亡":
            profile.set_status("死亡")
