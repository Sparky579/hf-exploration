"""
Module purpose:
- Manage global timeline, world states, battle target, companion runtime state, and scripted triggers.

Class:
- GlobalConfig
  - current_time_unit property: read/write current global time in range [0, 100].
  - advance_time(amount): move global time forward by amount, with boundary checks.
  - has_state/set_state/add_global_state/remove_global_state: global state list maintenance.
  - add_dynamic_state/remove_dynamic_state/list_dynamic_states: dynamic text state maintenance.
  - set_battle_state/clear_battle_state/is_battle_phase: battle target string state.
  - init_companion_registry(profiles): initialize companion fixed-format runtime storage.
  - companion state APIs: team/discovered/affection/noticed_by management.
  - add_scripted_trigger/remove_scripted_trigger/list_scripted_triggers: runtime trigger storage.
  - trigger helper APIs: mark fired/handled, query future triggers by owner.
  - list_triggers_until(end_time): query trigger rows in [current_time, end_time].
  - get_latest_trigger_time_for_owner(owner): query latest trigger time for one owner.
  - set_main_game_state(state): set main-player game install/download/device status.
  - can_main_player_gain_holy_water property: whether main player can regenerate holy water.
"""

from __future__ import annotations

import re
from typing import Any

from .constants import PHASE_BATTLE, PHASE_EMERGENCY


class GlobalConfig:
    """Global runtime config for timeline and world states."""

    MAIN_GAME_STATES = {
        "installed",
        "downloading",
        "not_installed",
        "confiscated",
    }

    def __init__(
        self,
        current_time_unit: float = 0.0,
        global_states: list[str] | None = None,
        dynamic_states: list[str] | None = None,
        battle_state: str | None = None,
        main_game_state: str = "installed",
    ) -> None:
        self._current_time_unit = 0.0
        self.current_time_unit = current_time_unit
        self.global_states = list(global_states or [])
        self.dynamic_states = list(dynamic_states or [])
        self.battle_state: str | None = None
        if battle_state is not None:
            self.set_battle_state(battle_state)
        self.main_game_state: str = "installed"
        self.set_main_game_state(main_game_state)

        # Fixed-format companion runtime store in global config.
        self.companions: dict[str, dict[str, Any]] = {}
        self.team_companions: list[str] = []

        # Dynamic scripted triggers added by story/model/system.
        # Item shape:
        # {
        #   "id": int, "text": str, "owner": str,
        #   "trigger_time": float, "condition": str, "result": str,
        #   "triggered": bool, "handled": bool,
        # }
        self.scripted_triggers: list[dict[str, Any]] = []
        self._next_trigger_id = 1

    @property
    def current_time_unit(self) -> float:
        return self._current_time_unit

    @current_time_unit.setter
    def current_time_unit(self, value: float) -> None:
        if not (0 <= value <= 100):
            raise ValueError("current_time_unit must be between 0 and 100.")
        self._current_time_unit = float(value)

    def advance_time(self, amount: float) -> float:
        if amount < 0:
            raise ValueError("amount must be >= 0.")
        next_time = self.current_time_unit + amount
        if next_time > 100:
            raise ValueError("time overflow: current_time_unit cannot exceed 100.")
        self.current_time_unit = next_time
        return self.current_time_unit

    def has_state(self, state: str) -> bool:
        return state in self.global_states

    def set_state(self, state: str, enabled: bool) -> None:
        if state == PHASE_BATTLE:
            self.set_battle_state("__BATTLE__" if enabled else None)
            return
        if enabled and state not in self.global_states:
            self.global_states.append(state)
        if not enabled and state in self.global_states:
            self.global_states.remove(state)

    def add_global_state(self, state: str) -> None:
        self.set_state(state, True)

    def remove_global_state(self, state: str) -> None:
        self.set_state(state, False)

    def add_dynamic_state(self, text: str) -> None:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("dynamic state text must be a non-empty string.")
        if text not in self.dynamic_states:
            self.dynamic_states.append(text)

    def remove_dynamic_state(self, text: str) -> None:
        if text in self.dynamic_states:
            self.dynamic_states.remove(text)

    def list_dynamic_states(self) -> list[str]:
        return list(self.dynamic_states)

    def set_battle_state(self, target: str | None) -> None:
        if target is None or not str(target).strip():
            self.battle_state = None
            if PHASE_BATTLE in self.global_states:
                self.global_states.remove(PHASE_BATTLE)
            return
        self.battle_state = str(target).strip()
        if PHASE_BATTLE not in self.global_states:
            self.global_states.append(PHASE_BATTLE)

    def clear_battle_state(self) -> None:
        self.set_battle_state(None)

    @property
    def is_emergency_phase(self) -> bool:
        return self.has_state(PHASE_EMERGENCY)

    @property
    def is_battle_phase(self) -> bool:
        return self.battle_state is not None

    @property
    def can_main_player_gain_holy_water(self) -> bool:
        return self.main_game_state == "installed"

    def set_main_game_state(self, state: str) -> None:
        normalized = self._normalize_main_game_state(state)
        if normalized not in self.MAIN_GAME_STATES:
            raise ValueError(
                "main_game_state must be one of: installed/downloading/not_installed/confiscated"
            )
        self.main_game_state = normalized

    def init_companion_registry(self, profiles: dict[str, Any]) -> None:
        """Initialize companion runtime data with a fixed storage format."""

        self.companions = {}
        for name, profile in profiles.items():
            self.companions[name] = {
                "name": getattr(profile, "name", name),
                "role_type": getattr(profile, "role_type", "friendly"),
                "home_node": getattr(profile, "home_node", ""),
                "move_time_cost": float(getattr(profile, "move_time_cost", 1.0)),
                "can_attack": bool(getattr(profile, "can_attack", False)),
                "deck": list(getattr(profile, "deck", [])),
                "description": str(getattr(profile, "description", "")),
                "discovered": False,
                "in_team": False,
                "affection": 0.0,
                "holy_water": 0.0,
                "noticed_by": [],
            }
        self.team_companions = []

    def get_companion_state(self, name: str) -> dict[str, Any]:
        if name not in self.companions:
            raise KeyError(f"companion not found: {name}")
        return self.companions[name]

    def set_companion_discovered(self, name: str, enabled: bool) -> None:
        state = self.get_companion_state(name)
        state["discovered"] = bool(enabled)

    def set_companion_in_team(self, name: str, enabled: bool) -> None:
        state = self.get_companion_state(name)
        state["in_team"] = bool(enabled)
        self._sync_team_companions()

    def set_team_companions(self, names: list[str]) -> None:
        desired = set(names)
        for name in self.companions:
            self.companions[name]["in_team"] = name in desired
        self._sync_team_companions()

    def list_team_companions(self) -> list[str]:
        return list(self.team_companions)

    def set_companion_affection(self, name: str, value: float) -> None:
        state = self.get_companion_state(name)
        state["affection"] = float(value)

    def add_companion_affection(self, name: str, delta: float) -> None:
        state = self.get_companion_state(name)
        state["affection"] = float(state["affection"]) + float(delta)

    def add_companion_noticer(self, name: str, hostile_name: str) -> None:
        state = self.get_companion_state(name)
        noticed_by: list[str] = state["noticed_by"]
        if hostile_name not in noticed_by:
            noticed_by.append(hostile_name)

    def remove_companion_noticer(self, name: str, hostile_name: str) -> None:
        state = self.get_companion_state(name)
        noticed_by: list[str] = state["noticed_by"]
        if hostile_name in noticed_by:
            noticed_by.remove(hostile_name)

    def get_effective_main_move_cost(self, base_cost: float) -> float:
        effective = float(base_cost)
        for name in self.team_companions:
            state = self.get_companion_state(name)
            effective = max(effective, float(state["move_time_cost"]))
        return effective

    def add_scripted_trigger(self, sentence: str) -> dict[str, Any]:
        """
        Add one scripted trigger.

        Accepted text formats:
        - "时间8 若A 则B"
        - "角色:颜宏帆|时间3 若A 则B"
        - Fallback: any sentence with a number; first number is used as trigger time.
        """

        if not isinstance(sentence, str) or not sentence.strip():
            raise ValueError("scripted trigger text must be a non-empty string.")
        normalized = sentence.strip()
        owner, body = self._extract_trigger_owner(normalized)
        trigger_time, condition, result = self._parse_scripted_trigger_sentence(body)

        existing = self._find_same_trigger(owner, trigger_time, condition, result)
        if existing is not None:
            return dict(existing)

        item = {
            "id": self._next_trigger_id,
            "text": normalized,
            "owner": owner,
            "trigger_time": trigger_time,
            "condition": condition,
            "result": result,
            "triggered": False,
            "handled": False,
        }
        self._next_trigger_id += 1
        self.scripted_triggers.append(item)
        return dict(item)

    def remove_scripted_trigger(self, trigger_id_or_text: str) -> bool:
        raw = str(trigger_id_or_text).strip()
        if not raw:
            return False
        for idx, item in enumerate(self.scripted_triggers):
            if str(item["id"]) == raw or str(item["text"]) == raw:
                del self.scripted_triggers[idx]
                return True
        return False

    def clear_scripted_triggers(self) -> None:
        self.scripted_triggers.clear()

    def list_scripted_triggers(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.scripted_triggers]

    def mark_trigger_fired(self, trigger_id: int) -> None:
        trigger = self.get_scripted_trigger(trigger_id)
        trigger["triggered"] = True

    def mark_trigger_handled(self, trigger_id: int) -> None:
        trigger = self.get_scripted_trigger(trigger_id)
        trigger["handled"] = True

    def get_scripted_trigger(self, trigger_id: int) -> dict[str, Any]:
        for item in self.scripted_triggers:
            if int(item["id"]) == int(trigger_id):
                return item
        raise KeyError(f"scripted trigger not found: {trigger_id}")

    def list_fired_unhandled_triggers(self, owner: str | None = None) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self.scripted_triggers:
            if not bool(item["triggered"]) or bool(item["handled"]):
                continue
            if owner is not None and str(item["owner"]) != owner:
                continue
            rows.append(dict(item))
        return rows

    def has_any_trigger_for_owner(self, owner: str) -> bool:
        return any(str(item["owner"]) == owner for item in self.scripted_triggers)

    def has_future_trigger_for_owner(self, owner: str, now: float | None = None) -> bool:
        current_time = self.current_time_unit if now is None else float(now)
        for item in self.scripted_triggers:
            if str(item["owner"]) != owner:
                continue
            if bool(item["handled"]):
                continue
            if bool(item["triggered"]):
                continue
            if float(item["trigger_time"]) > current_time:
                return True
        return False

    def get_latest_trigger_time_for_owner(self, owner: str) -> float | None:
        latest: float | None = None
        for item in self.scripted_triggers:
            if str(item["owner"]) != owner:
                continue
            value = float(item["trigger_time"])
            latest = value if latest is None else max(latest, value)
        return latest

    def list_triggers_until(
        self,
        end_time: float,
        include_handled: bool = True,
        owner: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return triggers with `current_time <= trigger_time <= end_time`.
        """

        start = float(self.current_time_unit)
        end = float(end_time)
        rows: list[dict[str, Any]] = []
        for item in self.scripted_triggers:
            if owner is not None and str(item["owner"]) != owner:
                continue
            if (not include_handled) and bool(item["handled"]):
                continue
            t = float(item["trigger_time"])
            if t < start or t > end:
                continue
            rows.append(dict(item))
        rows.sort(key=lambda x: (float(x["trigger_time"]), int(x["id"])))
        return rows

    @staticmethod
    def _extract_trigger_owner(text: str) -> tuple[str, str]:
        if "|" not in text:
            return "global", text
        head, body = text.split("|", 1)
        head = head.strip()
        body = body.strip()
        if head.startswith("角色:"):
            owner = head[len("角色:") :].strip() or "global"
            return owner, body
        if head.lower().startswith("owner:"):
            owner = head.split(":", 1)[1].strip() or "global"
            return owner, body
        return "global", text

    @staticmethod
    def _parse_scripted_trigger_sentence(text: str) -> tuple[float, str, str]:
        # Preferred format: "时间8 若xx 则yy" (also supports English keywords).
        match = re.match(
            r"^\s*(?:时间|time|t)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:单位)?\s*(?:若|if)\s*(.+?)\s*(?:则|then)\s*(.+?)\s*$",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            return float(match.group(1)), match.group(2).strip(), match.group(3).strip()

        # Fallback: extract first number as trigger time; keep sentence as result.
        number = re.search(r"([0-9]+(?:\.[0-9]+)?)", text)
        trigger_time = float(number.group(1)) if number else 0.0
        return trigger_time, "default_condition", text

    @staticmethod
    def _normalize_main_game_state(raw: str) -> str:
        text = str(raw).strip().lower()
        mapping = {
            "installed": "installed",
            "ready": "installed",
            "安装完成": "installed",
            "已安装": "installed",
            "下载中": "downloading",
            "downloading": "downloading",
            "updating": "downloading",
            "not_installed": "not_installed",
            "未安装": "not_installed",
            "未下载": "not_installed",
            "confiscated": "confiscated",
            "没收": "confiscated",
            "手机被收": "confiscated",
            "no_phone": "confiscated",
        }
        return mapping.get(text, text)

    def _find_same_trigger(
        self,
        owner: str,
        trigger_time: float,
        condition: str,
        result: str,
    ) -> dict[str, Any] | None:
        for item in self.scripted_triggers:
            if str(item["owner"]) != owner:
                continue
            if abs(float(item["trigger_time"]) - float(trigger_time)) > 1e-9:
                continue
            if str(item["condition"]) != condition:
                continue
            if str(item["result"]) != result:
                continue
            if bool(item["handled"]):
                continue
            return item
        return None

    def _sync_team_companions(self) -> None:
        self.team_companions = [name for name, state in self.companions.items() if bool(state["in_team"])]
