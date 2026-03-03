"""
Module purpose:
- Check story triggers whenever time advances and apply global state changes.

Built-in events:
- alert: triggered when `current_time > alert_trigger_time`.
- emergency: triggered after 德政楼 is destroyed and time check runs.
- explosion: triggered when `current_time >= emergency_start + emergency_blast_delay`.

Scripted events:
- Trigger sentence fires when `current_time >= trigger_time`.
- Supported auto result keywords:
  - `提示:<text>` / `预警:<text>` -> append global dynamic state.
  - `建筑倒塌:<name>` -> destroy mapped node(s), kill all roles at affected nodes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .constants import (
    GLOBAL_STATE_ALERT,
    GLOBAL_STATE_BARRIER_REMOVED,
    GLOBAL_STATE_COLLAPSE_PREFIX,
    GLOBAL_STATE_EMERGENCY,
    GLOBAL_STATE_GAME_INSTALL_DONE,
    GLOBAL_STATE_SCHOOL_EXPLOSION,
)
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

    OPENING_HOTSPOT_BRANCH = "开场分支:借马超鹏热点更新"
    OPENING_FLOW_BRANCH = "开场分支:流量更新"
    OPENING_NOTICE_DONE = "开场事件:马超鹏已在课堂提醒他也注意到了更新"
    OPENING_HANDOFF_DONE = "开场事件:马超鹏已主动交付主手机"
    OPENING_MAIN_PHONE_HELD = "开场事件:主控已持有马超鹏主手机"
    SOUTH_BUILDING_CHENLUO_DONE = "场景事件:南教学楼遭遇陈洛已触发"
    GATE_GUARD_BROKEN_MARKER: dict[str, str] = {
        "正门": "场景事件:正门保安防线已突破",
        "后门": "场景事件:后门保安防线已突破",
    }
    INTL_TEACHER_EXIT_BLOCKED = "场景事件:国际部信息老师封锁国际部出口"

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
        self._check_opening_phone_story(now)
        self._check_time_bound_departures(now)
        if (not self.state.alert_triggered) and now > self.story_setting.alert_trigger_time:
            self.state.alert_triggered = True
            self.engine.global_config.add_global_state(GLOBAL_STATE_ALERT)
            self.engine.global_config.add_dynamic_state("触发：学校进入警报状态")
            self.engine.global_config.add_dynamic_state("全校响起尖锐刺耳的警报声，几乎所有人都能听见。")
            self.state.trigger_history.append(f"t={now}: 警报状态触发")

        if (not self.state.emergency_triggered) and (not self.engine.campus_map.is_node_valid("德政楼")):
            self._trigger_emergency(now)

        if (
            self.state.emergency_triggered
            and (not self.state.explosion_triggered)
            and self.state.explosion_time is not None
            and now >= self.state.explosion_time
        ):
            self.state.explosion_triggered = True
            self.engine.global_config.add_global_state(GLOBAL_STATE_SCHOOL_EXPLOSION)
            self.engine.global_config.add_dynamic_state("触发：学校爆炸")
            self.state.trigger_history.append(f"t={now}: 学校爆炸触发")
            for role_name in list(self.engine.campus_map.roles.keys()):
                if role_name in self.state.escaped_roles:
                    continue
                self.engine.set_role_health(role_name, 0)
                self._mark_character_dead_if_exists(role_name)

        self._check_scripted_triggers(now)

    def _check_time_bound_departures(self, now: float) -> None:
        """
        Time-bound NPC departures:
        - 陈洛在 t>=11 且未触发南教学楼治疗事件时，视为离开校园。
        """
        if now < 11.0:
            return
        if "陈洛" not in self.engine.character_profiles:
            return
        profile = self.engine.get_character_profile("陈洛")
        if profile.status != "存活":
            return
        if self.SOUTH_BUILDING_CHENLUO_DONE in set(self.engine.global_config.dynamic_states):
            return

        profile.set_status("离开校园")
        if "陈洛" in self.engine.campus_map.roles:
            role = self.engine.get_role("陈洛")
            self.engine.campus_map.get_node(role.current_location).remove_role("陈洛")
            del self.engine.campus_map.roles["陈洛"]
        self.engine.global_config.add_dynamic_state("陈洛在混乱中离开校园，不再出现在场景内。")
        self.state.trigger_history.append(f"t={now}: 陈洛离场（超时未遭遇）")

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
        if self._is_gate_guard_blocking(node_name):
            return False
        if node_name == "国际部" and self.INTL_TEACHER_EXIT_BLOCKED in set(self.engine.global_config.dynamic_states):
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
        if self.engine.global_config.battle_state is not None:
            raise ValueError("escape is blocked: role is currently in battle.")
        if self._is_gate_guard_blocking(node_name):
            raise ValueError(
                f"escape is blocked by rigid guard at {node_name}; persuasion is impossible before breaking guard defense."
            )
        if node_name == "国际部" and self.INTL_TEACHER_EXIT_BLOCKED in set(self.engine.global_config.dynamic_states):
            raise ValueError("escape is blocked at 国际部: 信息老师正封锁出口，不允许翻出校园。")
        if not self.can_escape_from(node_name):
            raise ValueError(f"escape is not allowed from node now: {node_name}")
        self.state.escaped_roles.add(role_name)
        role.add_dynamic_state(f"已通过{node_name}逃离校园")
        self.state.trigger_history.append(
            f"t={self.engine.global_config.current_time_unit}: {role_name} 通过{node_name}逃离"
        )

    def _is_gate_guard_blocking(self, node_name: str) -> bool:
        if node_name not in self.GATE_GUARD_BROKEN_MARKER:
            return False
        marker = self.GATE_GUARD_BROKEN_MARKER[node_name]
        return marker not in set(self.engine.global_config.dynamic_states)

    def recent_trigger_history(self, limit: int = 15) -> list[str]:
        if limit <= 0:
            return []
        return self.state.trigger_history[-limit:]

    def collapse_structure_now(self, target: str, *, reason: str = "") -> None:
        """
        Public immediate collapse API (non-trigger path).
        Used by fixed backend events that should not materialize as scripted trigger text.
        """
        now = float(self.engine.global_config.current_time_unit)
        self._apply_structure_collapse(target=target, now=now)
        if reason.strip():
            self.state.trigger_history.append(f"t={now}: 直接坍塌({target}) <- {reason.strip()}")

    def _check_scripted_triggers(self, now: float) -> None:
        touched = False
        for item in self.engine.global_config.scripted_triggers:
            if bool(item["triggered"]):
                continue
            trigger_time = float(item["trigger_time"])
            if now < trigger_time:
                continue
            condition = str(item.get("condition", "")).strip()
            if condition and (not self._is_scripted_condition_met(condition)):
                continue
            item["triggered"] = True
            touched = True
            text = str(item["text"])
            self.engine.global_config.add_dynamic_state(f"脚本触发#{item['id']}: {text}")
            self.state.trigger_history.append(f"t={now}: 脚本触发#{item['id']} -> {text}")
            self._apply_scripted_result(item, now)
            item["handled"] = True
        if touched:
            self.engine.global_config.cleanup_scripted_triggers(now=now)

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

        death_marker = "角色死亡:"
        if death_marker in result:
            payload = result.split(death_marker, 1)[1].strip()
            if payload:
                if "|" in payload:
                    role_name, reason = payload.split("|", 1)
                else:
                    role_name, reason = payload, ""
                self._apply_character_death(role_name.strip(), reason.strip(), now)
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
            if self._is_role_protected_from_collapse(target, role_name):
                self.state.trigger_history.append(
                    f"t={now}: 坍塌豁免 -> {role_name} 于 {target}"
                )
                continue
            self.engine.set_role_health(role_name, 0)
            self._mark_character_dead_if_exists(role_name)

        # Winter Rain special rule:
        # if 图书馆 collapses and 冬雨 is not in main player's team, she is marked dead.
        self._apply_dongyu_library_collapse_rule(affected_nodes, now)
        if "德政楼" in affected_nodes:
            self._trigger_emergency(now)

        if affected_nodes:
            joined_nodes = ",".join(affected_nodes)
            self.engine.global_config.add_global_state(f"{GLOBAL_STATE_COLLAPSE_PREFIX}{target}")
            self.engine.global_config.add_dynamic_state(f"{target}坍塌，影响区域：{joined_nodes}")
            self.state.trigger_history.append(f"t={now}: 建筑倒塌 -> {target} ({joined_nodes})")

    @staticmethod
    def _is_role_protected_from_collapse(target: str, role_name: str) -> bool:
        # Deterministic script rule:
        # 黎诺存在西教学楼坍塌链路中视为远离主体坍塌点，保留后续火箭主线。
        if role_name == "黎诺存" and target in ("西教学楼", "西教学楼南", "西教学楼北"):
            return True
        return False

    def _trigger_emergency(self, now: float) -> None:
        if self.state.emergency_triggered:
            return
        self.state.emergency_triggered = True
        self.state.emergency_start_time = now
        self.state.explosion_time = now + self.story_setting.emergency_blast_delay
        self.engine.set_emergency_phase(True)
        self.engine.global_config.add_global_state(GLOBAL_STATE_EMERGENCY)
        self.engine.global_config.add_global_state(GLOBAL_STATE_BARRIER_REMOVED)
        self.engine.global_config.remove_global_state(GLOBAL_STATE_ALERT)
        self.engine.global_config.add_dynamic_state("触发：德政楼被摧毁，进入紧急状态")
        self.engine.global_config.add_dynamic_state("结界解除：校园边缘屏障已消失。")
        self.state.trigger_history.append(f"t={now}: 紧急状态触发，爆炸倒计时开始")

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

    def _apply_character_death(self, role_name: str, reason: str, now: float) -> None:
        if not role_name:
            return
        if role_name in self.engine.campus_map.roles:
            self.engine.set_role_health(role_name, 0)
        self._mark_character_dead_if_exists(role_name)
        if role_name in self.engine.global_config.companions:
            self.engine.set_companion_in_team(role_name, False)
        suffix = f"（{reason}）" if reason else ""
        self.engine.global_config.add_dynamic_state(f"{role_name}死亡{suffix}")
        self.state.trigger_history.append(f"t={now}: 角色死亡 -> {role_name}{suffix}")

    def _is_scripted_condition_met(self, condition: str) -> bool:
        text = condition.replace(" ", "")
        if text in ("许琪琪未被主角邀请入队", "许琪琪未被邀请入队", "未邀请许琪琪入队"):
            try:
                state = self.engine.global_config.get_companion_state("许琪琪")
            except KeyError:
                return True
            return not bool(state.get("in_team", False))
        return True

    def _apply_dongyu_library_collapse_rule(self, affected_nodes: list[str], now: float) -> None:
        if "图书馆" not in set(affected_nodes):
            return
        try:
            state = self.engine.global_config.get_companion_state("冬雨")
        except KeyError:
            return
        if bool(state.get("in_team", False)):
            return
        self._apply_character_death("冬雨", "图书馆坍塌", now)

    def _check_opening_phone_story(self, now: float) -> None:
        """
        Opening deterministic flow:
        - Hotspot branch at t>=2: add classroom notice that 马超鹏 also noticed the update.
        - Hotspot branch at t>=3 and main player still has no usable phone:
          马超鹏主动提出交付主手机, switch main deck.
        """

        states = set(self.engine.global_config.dynamic_states)
        if self.OPENING_HOTSPOT_BRANCH not in states:
            return

        if now >= 2 and self.OPENING_NOTICE_DONE not in states:
            self.engine.global_config.add_dynamic_state(
                "马超鹏低声提醒：他也注意到了这次超现实更新。"
            )
            self.engine.global_config.add_dynamic_state(self.OPENING_NOTICE_DONE)
            self.state.trigger_history.append(f"t={now}: 开场事件 -> 马超鹏提醒更新")

        if now < 3 or self.OPENING_HANDOFF_DONE in states:
            return
        if self.engine.main_player_name is None:
            return

        # Only force handoff when the main player still has no usable client/phone.
        if self.engine.global_config.main_game_state not in ("confiscated", "not_installed", "downloading"):
            return

        main_name = self.engine.main_player_name
        self.engine.set_companion_discovered("马超鹏", True)
        self.engine.set_companion_in_team("马超鹏", True)
        ma_profile = self.engine.get_companion_profile("马超鹏")
        self.engine.set_player_card_deck(main_name, list(ma_profile.deck))
        self.engine.set_main_game_state("installed")
        self.engine.set_player_holy_water(main_name, 0.0)
        self.engine.global_config.add_global_state(GLOBAL_STATE_GAME_INSTALL_DONE)
        self.engine.global_config.add_dynamic_state(
            "骷髅骚乱爆发时，马超鹏主动把他的主手机塞给了你；你原本被收走的手机从此无法找回。"
        )
        self.engine.global_config.add_dynamic_state(self.OPENING_MAIN_PHONE_HELD)
        self.engine.global_config.add_dynamic_state(self.OPENING_HANDOFF_DONE)
        self.state.trigger_history.append(f"t={now}: 开场事件 -> 马超鹏交机并切换主控卡组")
