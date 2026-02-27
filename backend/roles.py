"""
Module purpose:
- Define map role behavior and player battle behavior.

Classes:
- Role
  - query_current_location(): return role's current node.
  - query_movement_status(): return moving state plus from/to fields.
  - _start_move(target): internal helper called by engine when move begins.
  - _finish_move(target): internal helper called by engine when move ends.
- PlayerRole (extends Role)
  - holy_water_rate_per_time(): compute current regen rate from global phase.
  - regenerate_holy_water(dt): add holy water by dt and current multiplier.
  - deploy_unit(unit_name, node_name): spawn player unit, mark wartime if battle phase.
  - remove_unit(unit_id): remove one unit from active list.
  - clear_wartime_units(): remove all wartime units when battle phase ends.
  - list_active_units(): return runtime unit list.
  - select_attack_target(...): enforce targeting priority and manual-target rules.
"""

from __future__ import annotations

from .constants import BASE_HOLY_WATER_PER_TIME
from .global_config import GlobalConfig
from .map_core import CampusMap
from .units import DeployedUnit, TargetKind, UnitCard, build_default_unit_cards


class Role:
    """Role with location + queued movement status."""

    def __init__(
        self,
        name: str,
        campus_map: CampusMap,
        global_config: GlobalConfig,
        start_location: str,
    ) -> None:
        self.name = name
        self._campus_map = campus_map
        self._global_config = global_config
        self._current_location = start_location
        self._moving_to: str | None = None
        self._campus_map.add_role(self, start_location)

    @property
    def current_location(self) -> str:
        return self._current_location

    @property
    def is_moving(self) -> bool:
        return self._moving_to is not None

    def query_current_location(self) -> str:
        return self._current_location

    def query_movement_status(self) -> dict[str, str | bool | None]:
        return {
            "role_name": self.name,
            "is_moving": self.is_moving,
            "from": self._current_location,
            "to": self._moving_to,
        }

    def _start_move(self, target_node_name: str) -> None:
        self._moving_to = target_node_name

    def _finish_move(self, target_node_name: str) -> None:
        self._current_location = target_node_name
        self._moving_to = None


class PlayerRole(Role):
    """Player role with holy-water economy and unit management."""

    def __init__(
        self,
        name: str,
        campus_map: CampusMap,
        global_config: GlobalConfig,
        start_location: str,
        available_cards: list[UnitCard] | None = None,
    ) -> None:
        super().__init__(name, campus_map, global_config, start_location)
        self.holy_water: float = 0.0
        cards = available_cards if available_cards is not None else build_default_unit_cards()
        self.available_cards: dict[str, UnitCard] = {card.name: card for card in cards}
        self.active_units: dict[str, DeployedUnit] = {}
        self._next_unit_seq = 1

    def holy_water_rate_per_time(self) -> float:
        multiplier = 1.0
        if self._global_config.is_emergency_phase:
            multiplier *= 2.0
        if self._global_config.is_battle_phase:
            multiplier *= 4.0
        return BASE_HOLY_WATER_PER_TIME * multiplier

    def regenerate_holy_water(self, time_delta: float) -> float:
        if time_delta < 0:
            raise ValueError("time_delta must be >= 0.")
        self.holy_water += self.holy_water_rate_per_time() * time_delta
        return self.holy_water

    def deploy_unit(self, unit_name: str, node_name: str | None = None) -> DeployedUnit:
        if unit_name not in self.available_cards:
            raise KeyError(f"unit card not found: {unit_name}")

        spawn_node = node_name or self.current_location
        self._campus_map.get_node(spawn_node)

        unit_id = f"{self.name}-U{self._next_unit_seq}"
        self._next_unit_seq += 1

        card = self.available_cards[unit_name]
        deployed = DeployedUnit(
            unit_id=unit_id,
            owner_name=self.name,
            card=card,
            current_health=card.health,
            node_name=spawn_node,
            is_wartime=self._global_config.is_battle_phase,
            deployed_time=self._global_config.current_time_unit,
        )
        self.active_units[unit_id] = deployed
        return deployed

    def remove_unit(self, unit_id: str) -> None:
        if unit_id in self.active_units:
            del self.active_units[unit_id]

    def clear_wartime_units(self) -> list[str]:
        removed_ids = [uid for uid, unit in self.active_units.items() if unit.is_wartime]
        for uid in removed_ids:
            del self.active_units[uid]
        return removed_ids

    def list_active_units(self) -> list[DeployedUnit]:
        return list(self.active_units.values())

    def select_attack_target(
        self,
        unit_id: str,
        enemy_unit_ids: list[str],
        enemy_building_ids: list[str],
        enemy_npc_ids: list[str],
        field_building_ids: list[str],
        manual_target_id: str | None = None,
        manual_target_kind: TargetKind | None = None,
    ) -> tuple[TargetKind, str]:
        if unit_id not in self.active_units:
            raise KeyError(f"active unit not found: {unit_id}")
        unit = self.active_units[unit_id]

        has_combat_targets = bool(enemy_unit_ids or enemy_building_ids)
        if has_combat_targets:
            if unit.card.attack_preference == "prefer_building":
                if enemy_building_ids:
                    return ("enemy_building", enemy_building_ids[0])
                return ("enemy_unit", enemy_unit_ids[0])

            if unit.card.attack_preference == "manual_spell":
                if manual_target_kind in ("enemy_unit", "enemy_building") and manual_target_id:
                    if manual_target_kind == "enemy_unit" and manual_target_id in enemy_unit_ids:
                        return (manual_target_kind, manual_target_id)
                    if manual_target_kind == "enemy_building" and manual_target_id in enemy_building_ids:
                        return (manual_target_kind, manual_target_id)
                raise ValueError("spell unit must manually select an enemy unit/building in range first.")

            if enemy_unit_ids:
                return ("enemy_unit", enemy_unit_ids[0])
            return ("enemy_building", enemy_building_ids[0])

        if manual_target_kind == "enemy_npc" and manual_target_id in enemy_npc_ids:
            return (manual_target_kind, manual_target_id)
        if manual_target_kind == "field_building" and manual_target_id in field_building_ids:
            return (manual_target_kind, manual_target_id)
        raise ValueError("no enemy unit/building in range; manual target must be valid enemy_npc/field_building.")
