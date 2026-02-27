"""
Module purpose:
- Provide a single game-time driver so movement and resource regen are resolved in parallel.

Data classes:
- MovementTask: one queued movement command with remaining travel time.

Class:
- GameEngine
  - register_player(player): register a player for automatic holy-water regeneration.
  - issue_move(role_name, target_node_name): enqueue one-edge movement for role.
  - advance_time(amount): the only API that advances time and resolves queued systems.
  - set_emergency_phase(enabled): toggle emergency global state.
  - set_battle_phase(enabled): toggle battle state and clear wartime units on battle end.
  - add_global_dynamic_state(text): append one dynamic text to global config.
  - add_role_dynamic_state(role_name, text): append one dynamic text to a role.
  - set_role_location(role_name, node_name): force-update role map location.
  - set_role_health(role_name, value): set role health.
  - set_player_holy_water(player_name, value): set player holy-water amount.
  - _progress_movements(amount): internal movement simulation update.
  - _regenerate_players(amount): internal holy-water tick update.
"""

from __future__ import annotations

from dataclasses import dataclass

from .constants import MOVE_TIME_COST, PHASE_BATTLE, PHASE_EMERGENCY
from .global_config import GlobalConfig
from .map_core import CampusMap
from .roles import PlayerRole, Role


@dataclass
class MovementTask:
    role_name: str
    from_node: str
    to_node: str
    remaining_time: float = MOVE_TIME_COST


class GameEngine:
    """Unified time source for parallel movement and resource regeneration."""

    def __init__(self, campus_map: CampusMap, global_config: GlobalConfig) -> None:
        self.campus_map = campus_map
        self.global_config = global_config
        self.players: dict[str, PlayerRole] = {}
        self._movement_tasks: dict[str, MovementTask] = {}

    def register_player(self, player: PlayerRole) -> None:
        if player.name in self.players:
            raise ValueError(f"player already registered: {player.name}")
        self.players[player.name] = player

    def get_role(self, role_name: str) -> Role:
        if role_name not in self.campus_map.roles:
            raise KeyError(f"role not found: {role_name}")
        return self.campus_map.roles[role_name]

    def get_player(self, player_name: str) -> PlayerRole:
        if player_name not in self.players:
            raise KeyError(f"player not registered: {player_name}")
        return self.players[player_name]

    def issue_move(self, role_name: str, target_node_name: str) -> MovementTask:
        role = self.get_role(role_name)
        if role_name in self._movement_tasks:
            raise ValueError(f"role is already moving: {role_name}")

        current_node_name = role.current_location
        current_node = self.campus_map.get_node(current_node_name)
        if target_node_name not in current_node.neighbors:
            raise ValueError(
                f"cannot move from '{current_node_name}' to '{target_node_name}': not adjacent"
            )

        task = MovementTask(
            role_name=role_name,
            from_node=current_node_name,
            to_node=target_node_name,
            remaining_time=MOVE_TIME_COST,
        )
        self._movement_tasks[role_name] = task
        role._start_move(target_node_name)
        return task

    def advance_time(self, amount: float) -> float:
        if amount < 0:
            raise ValueError("amount must be >= 0.")
        if amount == 0:
            return self.global_config.current_time_unit

        self.global_config.advance_time(amount)
        self._progress_movements(amount)
        self._regenerate_players(amount)
        return self.global_config.current_time_unit

    def set_emergency_phase(self, enabled: bool) -> None:
        self.global_config.set_state(PHASE_EMERGENCY, enabled)

    def set_battle_phase(self, enabled: bool) -> None:
        was_battle = self.global_config.is_battle_phase
        self.global_config.set_state(PHASE_BATTLE, enabled)
        if was_battle and not self.global_config.is_battle_phase:
            for player in self.players.values():
                player.clear_wartime_units()

    def add_global_dynamic_state(self, text: str) -> None:
        self.global_config.add_dynamic_state(text)

    def add_role_dynamic_state(self, role_name: str, text: str) -> None:
        role = self.get_role(role_name)
        role.add_dynamic_state(text)

    def set_role_location(self, role_name: str, node_name: str) -> None:
        role = self.get_role(role_name)
        self.campus_map.get_node(node_name)
        old_node = role.current_location
        if role_name in self._movement_tasks:
            del self._movement_tasks[role_name]
            role._finish_move(old_node)
        self.campus_map.transfer_role(role_name, old_node, node_name)
        role._finish_move(node_name)

    def set_role_health(self, role_name: str, value: float) -> None:
        role = self.get_role(role_name)
        role.set_health(value)

    def set_player_holy_water(self, player_name: str, value: float) -> None:
        player = self.get_player(player_name)
        if value < 0:
            raise ValueError("holy_water must be >= 0.")
        player.holy_water = float(value)

    def _progress_movements(self, amount: float) -> None:
        completed: list[MovementTask] = []
        for task in self._movement_tasks.values():
            task.remaining_time -= amount
            if task.remaining_time <= 1e-9:
                completed.append(task)

        for task in completed:
            role = self.get_role(task.role_name)
            self.campus_map.transfer_role(task.role_name, task.from_node, task.to_node)
            role._finish_move(task.to_node)
            del self._movement_tasks[task.role_name]

    def _regenerate_players(self, amount: float) -> None:
        for player in self.players.values():
            player.regenerate_holy_water(amount)
