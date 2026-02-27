"""
Module purpose:
- Manage global timeline, world states, battle target, companion runtime state, and scripted story triggers.

Class:
- GlobalConfig
  - current_time_unit property: read/write current global time in range [0, 100].
  - advance_time(amount): move global time forward by amount, with boundary checks.
  - has_state/set_state/add_global_state/remove_global_state: global state list maintenance.
  - add_dynamic_state/remove_dynamic_state/list_dynamic_states: dynamic text state maintenance.
  - set_battle_state/clear_battle_state/is_battle_phase: battle target string state.
  - init_companion_registry(profiles): initialize companion fixed-format runtime storage.
  - get_companion_state/list_team_companions/set_team_companions: companion team state APIs.
  - set_companion_discovered/set_companion_in_team: companion boolean flags.
  - set_companion_affection/add_companion_affection: affection maintenance.
  - add_companion_noticer/remove_companion_noticer: noticed-by hostile list maintenance.
  - get_effective_main_move_cost(base): compute main-player move cost using team companions.
  - add_scripted_trigger/remove_scripted_trigger/list_scripted_triggers: runtime text trigger storage.
"""

from __future__ import annotations

import re
from typing import Any

from .constants import PHASE_BATTLE, PHASE_EMERGENCY


class GlobalConfig:
    """Global runtime config for timeline and world states."""

    def __init__(
        self,
        current_time_unit: float = 0.0,
        global_states: list[str] | None = None,
        dynamic_states: list[str] | None = None,
        battle_state: str | None = None,
    ) -> None:
        self._current_time_unit = 0.0
        self.current_time_unit = current_time_unit
        self.global_states = list(global_states or [])
        self.dynamic_states = list(dynamic_states or [])
        self.battle_state: str | None = None
        if battle_state is not None:
            self.set_battle_state(battle_state)

        # Fixed-format companion runtime store in global config.
        self.companions: dict[str, dict[str, Any]] = {}
        self.team_companions: list[str] = []

        # Dynamic scripted triggers added by config/story/model.
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
        if not isinstance(sentence, str) or not sentence.strip():
            raise ValueError("scripted trigger text must be a non-empty string.")
        normalized = sentence.strip()
        trigger_time, condition, result = self._parse_scripted_trigger_sentence(normalized)
        item = {
            "id": self._next_trigger_id,
            "text": normalized,
            "trigger_time": trigger_time,
            "condition": condition,
            "result": result,
            "triggered": False,
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
        for item in self.scripted_triggers:
            if int(item["id"]) == int(trigger_id):
                item["triggered"] = True
                return
        raise KeyError(f"scripted trigger not found: {trigger_id}")

    @staticmethod
    def _parse_scripted_trigger_sentence(text: str) -> tuple[float, str, str]:
        # Preferred format: "时间8 若xx 则yy" or "8时刻 若xx 则yy"
        match = re.match(
            r"^\s*(?:时间|时刻)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:单位)?\s*若\s*(.+?)\s*则\s*(.+?)\s*$",
            text,
        )
        if match:
            return float(match.group(1)), match.group(2).strip(), match.group(3).strip()

        # Fallback: extract first number as trigger time; keep original sentence as result.
        number = re.search(r"([0-9]+(?:\.[0-9]+)?)", text)
        trigger_time = float(number.group(1)) if number else 0.0
        return trigger_time, "默认条件", text

    def _sync_team_companions(self) -> None:
        self.team_companions = [name for name, state in self.companions.items() if bool(state["in_team"])]
