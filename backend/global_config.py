"""
Module purpose:
- Manage global timeline and global string states for the whole game world.

Class:
- GlobalConfig
  - current_time_unit property: read/write current global time in range [0, 100].
  - advance_time(amount): move global time forward by amount, with boundary checks.
  - has_state(state): check if a global state exists.
  - set_state(state, enabled): add/remove a global state in one call.
  - add_global_state(state): backward-compatible add wrapper.
  - remove_global_state(state): backward-compatible remove wrapper.
  - add_dynamic_state(text): append a dynamic runtime string (supports Chinese).
  - remove_dynamic_state(text): remove one dynamic runtime string.
  - list_dynamic_states(): return dynamic runtime strings.
  - is_emergency_phase: True when emergency state exists.
  - is_battle_phase: True when battle state exists.
"""

from __future__ import annotations

from .constants import PHASE_BATTLE, PHASE_EMERGENCY


class GlobalConfig:
    """Global runtime config for timeline and world states."""

    def __init__(
        self,
        current_time_unit: float = 0.0,
        global_states: list[str] | None = None,
        dynamic_states: list[str] | None = None,
    ) -> None:
        self._current_time_unit = 0.0
        self.current_time_unit = current_time_unit
        self.global_states = list(global_states or [])
        self.dynamic_states = list(dynamic_states or [])

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

    @property
    def is_emergency_phase(self) -> bool:
        return self.has_state(PHASE_EMERGENCY)

    @property
    def is_battle_phase(self) -> bool:
        return self.has_state(PHASE_BATTLE)
