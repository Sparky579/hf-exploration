"""
Module purpose:
- Provide a single game-time driver so movement, regen, and queue tasks are resolved consistently.

Data classes:
- MovementTask: one queued movement command with remaining travel time.

Class:
- GameEngine
  - register_player(player): register a player for automatic holy-water regeneration.
  - get_role/get_player: fetch role/player object by name.
  - issue_move(role_name, target_node_name): enqueue one-edge movement for role.
  - advance_time(amount): advance world time and resolve queued systems.
  - set_emergency_phase(enabled): toggle emergency phase.
  - set_battle_phase(enabled): compatibility wrapper for boolean battle on/off.
  - set_battle_state(target): set global battle state string (who is being fought).
  - add_global_dynamic_state/add_role_dynamic_state: append dynamic text states.
  - set_node_valid(node_name, valid): mark map node valid/destroyed.
  - set_role_location/set_role_health/set_role_battle_target: role state writes.
  - set_player_holy_water: player holy-water write.
  - set_character_status/add_character_history/remove_character_history/set_character_deck/set_character_description:
    static character profile maintenance.
  - _progress_movements/_regenerate_players: internal tick helpers.
"""

from __future__ import annotations

from dataclasses import dataclass

from .character_profiles import CharacterProfile, build_default_character_profiles
from .constants import MOVE_TIME_COST, PHASE_EMERGENCY
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
    """Unified time source for world updates."""

    def __init__(self, campus_map: CampusMap, global_config: GlobalConfig) -> None:
        self.campus_map = campus_map
        self.global_config = global_config
        self.players: dict[str, PlayerRole] = {}
        self._movement_tasks: dict[str, MovementTask] = {}
        self.character_profiles: dict[str, CharacterProfile] = build_default_character_profiles()

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

    def get_character_profile(self, name: str) -> CharacterProfile:
        if name not in self.character_profiles:
            raise KeyError(f"character profile not found: {name}")
        return self.character_profiles[name]

    def issue_move(self, role_name: str, target_node_name: str) -> MovementTask:
        role = self.get_role(role_name)
        if role_name in self._movement_tasks:
            raise ValueError(f"role is already moving: {role_name}")

        target_node = self.campus_map.get_node(target_node_name)
        if not target_node.valid:
            raise ValueError(f"cannot move to destroyed node: {target_node_name}")

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
        self.set_battle_state("__BATTLE__" if enabled else None)

    def set_battle_state(self, target: str | None) -> None:
        was_battle = self.global_config.is_battle_phase
        self.global_config.set_battle_state(target)
        if was_battle and not self.global_config.is_battle_phase:
            for player in self.players.values():
                player.clear_wartime_units()

    def add_global_dynamic_state(self, text: str) -> None:
        self.global_config.add_dynamic_state(text)

    def add_role_dynamic_state(self, role_name: str, text: str) -> None:
        role = self.get_role(role_name)
        role.add_dynamic_state(text)

    def set_node_valid(self, node_name: str, valid: bool) -> None:
        self.campus_map.set_node_valid(node_name, valid)

    def set_role_location(self, role_name: str, node_name: str) -> None:
        role = self.get_role(role_name)
        target_node = self.campus_map.get_node(node_name)
        if not target_node.valid:
            raise ValueError(f"cannot set location to destroyed node: {node_name}")
        old_node = role.current_location
        if role_name in self._movement_tasks:
            del self._movement_tasks[role_name]
            role._finish_move(old_node)
        self.campus_map.transfer_role(role_name, old_node, node_name)
        role._finish_move(node_name)

    def set_role_health(self, role_name: str, value: float) -> None:
        role = self.get_role(role_name)
        role.set_health(value)

    def set_role_battle_target(self, role_name: str, target: str | None) -> None:
        role = self.get_role(role_name)
        role.set_battle_target(target)

    def set_player_holy_water(self, player_name: str, value: float) -> None:
        player = self.get_player(player_name)
        if value < 0:
            raise ValueError("holy_water must be >= 0.")
        player.holy_water = float(value)

    def set_character_status(self, name: str, status: str) -> None:
        self.get_character_profile(name).set_status(status)

    def add_character_history(self, name: str, text: str) -> None:
        self.get_character_profile(name).add_history(text)

    def remove_character_history(self, name: str, text: str) -> None:
        self.get_character_profile(name).remove_history(text)

    def set_character_deck(self, name: str, deck: list[str]) -> None:
        self.get_character_profile(name).set_card_deck(deck)

    def set_character_description(self, name: str, text: str) -> None:
        profile = self.get_character_profile(name)
        if not text.strip():
            raise ValueError("description must be non-empty.")
        profile.description = text

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
