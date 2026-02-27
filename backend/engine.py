"""
Module purpose:
- Provide a single game-time driver so movement and resource regen are resolved in parallel.

Data classes:
- MovementTask: one queued movement command with remaining travel time.

Class:
- GameEngine
  - register_player(player): register a player for automatic holy-water regeneration.
  - issue_move(role_name, target_node_name): enqueue one edge movement for role.
  - advance_time(amount): the only API that advances time and resolves all queued systems.
  - set_emergency_phase(enabled): toggle emergency global state.
  - set_battle_phase(enabled): toggle battle state and clear wartime units on battle end.
  - _progress_movements(amount): internal movement simulation update.
  - _regenerate_players(amount): internal holy-water tick update for all players.
"""

from __future__ import annotations

from dataclasses import dataclass

from .constants import MOVE_TIME_COST, PHASE_BATTLE, PHASE_EMERGENCY
from .global_config import GlobalConfig
from .map_core import CampusMap
from .roles import PlayerRole


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

    def issue_move(self, role_name: str, target_node_name: str) -> MovementTask:
        if role_name not in self.campus_map.roles:
            raise KeyError(f"role not found: {role_name}")
        if role_name in self._movement_tasks:
            raise ValueError(f"role is already moving: {role_name}")

        role = self.campus_map.roles[role_name]
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

    def _progress_movements(self, amount: float) -> None:
        completed: list[MovementTask] = []
        for task in self._movement_tasks.values():
            task.remaining_time -= amount
            if task.remaining_time <= 1e-9:
                completed.append(task)

        for task in completed:
            role = self.campus_map.roles[task.role_name]
            self.campus_map.transfer_role(task.role_name, task.from_node, task.to_node)
            role._finish_move(task.to_node)
            del self._movement_tasks[task.role_name]

    def _regenerate_players(self, amount: float) -> None:
        for player in self.players.values():
            player.regenerate_holy_water(amount)
