"""
Module purpose:
- Check story triggers whenever time advances and apply global state changes.

Events:
- alert: triggered when current_time > alert_trigger_time.
- emergency: triggered after 德政楼 is destroyed and time check runs.
- explosion: triggered when current_time > emergency_start + emergency_blast_delay.

Rules:
- Before alert: escape allowed at story-configured nodes.
- After alert: normal escape is disabled.
- During emergency window: escape re-enabled at configured nodes.
- 国际部 escape requires 国际部 node still valid.
- Main player HP <= 0 means immediate game over.
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
