"""
Module purpose:
- Define map role behavior and player battle behavior.

Classes:
- Role
  - query_current_location(): return role's current node.
  - query_movement_status(): return moving state plus from/to fields.
  - set_health(value): set role health (>=0).
  - set_battle_target(target): set current battle target string for this role.
  - clear_battle_target(): clear current battle target.
  - add_dynamic_state/remove_dynamic_state/list_dynamic_states(): manage role dynamic text states.
  - set_nearby_unit_status(name, status): set one nearby unit tag ("full"/"damaged"), "dead" removes it.
  - replace_nearby_units(items): replace nearby unit map by name->status.
  - list_nearby_units(): return current nearby unit map copy.
  - _start_move/_finish_move(): internal hooks called by engine.
- PlayerRole (extends Role)
  - holy_water_rate_per_time(): compute regen rate from global phase.
  - regenerate_holy_water(dt): add holy water by dt and current multiplier.
  - deploy_unit(unit_name, node_name): deploy by explicit unit card name.
  - deploy_from_deck(card_name=None, node_name=None): deploy using playable deck cards then rotate deck.
  - rotate_card_deck(): shift first deck card to the end.
  - playable_cards(): return current playable prefix cards.
  - remove_unit/clear_wartime_units/list_active_units(): deployed-unit maintenance.
  - select_attack_target(...): enforce target-priority and manual-target rules.
"""

from __future__ import annotations

from .constants import BASE_HOLY_WATER_PER_TIME
from .global_config import GlobalConfig
from .map_core import CampusMap
from .units import DeployedUnit, NearbyUnitStatus, TargetKind, UnitCard, build_all_unit_cards, build_default_unit_cards


class Role:
    """Role with location, health, nearby unit states, and queued movement status."""

    def __init__(
        self,
        name: str,
        campus_map: CampusMap,
        global_config: GlobalConfig,
        start_location: str,
        health: float = 10,
    ) -> None:
        self.name = name
        self._campus_map = campus_map
        self._global_config = global_config
        self._current_location = start_location
        self._moving_to: str | None = None
        self.health = float(health)
        self.battle_target: str | None = None
        self.dynamic_states: list[str] = []
        self.nearby_units: dict[str, NearbyUnitStatus] = {}
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

    def set_health(self, value: float) -> None:
        if value < 0:
            raise ValueError("health must be >= 0.")
        self.health = float(value)

    def set_battle_target(self, target: str | None) -> None:
        if target is None or not str(target).strip():
            self.battle_target = None
            return
        self.battle_target = str(target).strip()

    def clear_battle_target(self) -> None:
        self.battle_target = None

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

    def set_nearby_unit_status(self, unit_name: str, status: str) -> None:
        if status == "dead":
            self.nearby_units.pop(unit_name, None)
            return
        if status not in ("full", "damaged"):
            raise ValueError("nearby unit status must be 'full', 'damaged', or 'dead'.")
        self.nearby_units[unit_name] = status  # type: ignore[assignment]

    def replace_nearby_units(self, items: dict[str, str]) -> None:
        replaced: dict[str, NearbyUnitStatus] = {}
        for unit_name, status in items.items():
            if status not in ("full", "damaged"):
                raise ValueError("replace_nearby_units accepts only 'full' or 'damaged'.")
            replaced[unit_name] = status  # type: ignore[assignment]
        self.nearby_units = replaced

    def list_nearby_units(self) -> dict[str, NearbyUnitStatus]:
        return dict(self.nearby_units)

    def _start_move(self, target_node_name: str) -> None:
        self._moving_to = target_node_name

    def _finish_move(self, target_node_name: str) -> None:
        self._current_location = target_node_name
        self._moving_to = None


class PlayerRole(Role):
    """Player role with holy-water economy, card deck, and deployed unit management."""

    def __init__(
        self,
        name: str,
        campus_map: CampusMap,
        global_config: GlobalConfig,
        start_location: str,
        available_cards: list[UnitCard] | None = None,
        card_deck: list[str] | None = None,
        card_valid: int = 4,
        health: float = 10,
    ) -> None:
        super().__init__(name, campus_map, global_config, start_location, health=health)
        self.holy_water: float = 0.0
        cards = available_cards if available_cards is not None else build_all_unit_cards()
        self.available_cards: dict[str, UnitCard] = {card.name: card for card in cards}
        self.active_units: dict[str, DeployedUnit] = {}
        self._next_unit_seq = 1

        default_deck = [card.name for card in build_default_unit_cards()]
        self.card_deck: list[str] = list(card_deck or default_deck)
        self.card_valid = int(card_valid)
        self._validate_deck()

    def _validate_deck(self) -> None:
        if len(self.card_deck) != 8:
            raise ValueError("card_deck must contain exactly 8 cards.")
        for idx, card_name in enumerate(self.card_deck):
            self.card_deck[idx] = self._resolve_known_card_name(card_name)
        if not (1 <= self.card_valid <= 8):
            raise ValueError("card_valid must be between 1 and 8.")

    def set_card_valid(self, value: int) -> None:
        if not (1 <= int(value) <= 8):
            raise ValueError("card_valid must be between 1 and 8.")
        self.card_valid = int(value)

    def set_card_deck(self, deck: list[str]) -> None:
        if len(deck) != 8:
            raise ValueError("card_deck must contain exactly 8 cards.")
        normalized = [self._resolve_known_card_name(name) for name in deck]
        self.card_deck = normalized

    def playable_cards(self) -> list[str]:
        return list(self.card_deck[: self.card_valid])

    def rotate_card_deck(self) -> None:
        first = self.card_deck.pop(0)
        self.card_deck.append(first)

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
        unit_name = self._resolve_known_card_name(unit_name)

        card = self.available_cards[unit_name]
        if self.holy_water < card.consume:
            raise ValueError(f"holy water is not enough: need {card.consume}, current {self.holy_water}")

        spawn_node = node_name or self.current_location
        spawn = self._campus_map.get_node(spawn_node)
        if not spawn.valid:
            raise ValueError(f"cannot deploy at destroyed node: {spawn_node}")
        self.holy_water -= card.consume

        unit_id = f"{self.name}-U{self._next_unit_seq}"
        self._next_unit_seq += 1
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

    def deploy_from_deck(self, card_name: str | None = None, node_name: str | None = None) -> DeployedUnit:
        candidates = self.playable_cards()
        if not candidates:
            raise ValueError("no playable cards in current deck window.")
        chosen = self._resolve_known_card_name(card_name) if card_name else candidates[0]
        if chosen not in candidates:
            raise ValueError(f"card is not currently playable: {chosen}")
        deployed = self.deploy_unit(chosen, node_name=node_name)
        self.rotate_card_deck()
        return deployed

    def _resolve_known_card_name(self, raw_name: str) -> str:
        text = str(raw_name).strip()
        if text in self.available_cards:
            return text
        compact = "".join(text.split())
        for name in self.available_cards:
            if "".join(name.split()) == compact:
                return name
        raise ValueError(f"unknown card: {raw_name}")

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
