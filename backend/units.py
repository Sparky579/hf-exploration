"""
Module purpose:
- Define combat unit schemas and default unit-card pool.

Type aliases:
- UnitClass: "unit" | "building" | "spell".
- AttackPreference: targeting preference strategy.
- TargetKind: target category returned by targeting logic.

Data classes:
- UnitCard: static card data (attack, hp, speed, flying, class, preference).
- DeployedUnit: runtime unit instance controlled by a player.

Functions:
- build_default_unit_cards(): return the configured default player unit cards.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

UnitClass = Literal["unit", "building", "spell"]
AttackPreference = Literal["prefer_unit", "prefer_building", "manual_spell"]
TargetKind = Literal["enemy_unit", "enemy_building", "enemy_npc", "field_building"]


@dataclass(frozen=True)
class UnitCard:
    name: str
    attack: float
    health: float
    move_speed: float
    is_flying: bool
    unit_class: UnitClass
    attack_preference: AttackPreference


@dataclass
class DeployedUnit:
    unit_id: str
    owner_name: str
    card: UnitCard
    current_health: float
    node_name: str
    is_wartime: bool
    deployed_time: float


def build_default_unit_cards() -> list[UnitCard]:
    """Default unit pool from requirement list."""

    return [
        UnitCard("地狱飞龙", attack=180, health=1100, move_speed=1.6, is_flying=True, unit_class="unit", attack_preference="prefer_unit"),
        UnitCard("电磁炮", attack=320, health=1600, move_speed=0.0, is_flying=False, unit_class="building", attack_preference="prefer_building"),
        UnitCard("巨人", attack=120, health=3500, move_speed=1.0, is_flying=False, unit_class="unit", attack_preference="prefer_building"),
        UnitCard("飓风法术", attack=40, health=1, move_speed=0.0, is_flying=False, unit_class="spell", attack_preference="manual_spell"),
        UnitCard("飞斧屠夫", attack=140, health=1000, move_speed=1.2, is_flying=False, unit_class="unit", attack_preference="prefer_unit"),
        UnitCard("骷髅军团", attack=45, health=120, move_speed=1.8, is_flying=False, unit_class="unit", attack_preference="prefer_unit"),
        UnitCard("亡灵", attack=65, health=150, move_speed=1.9, is_flying=True, unit_class="unit", attack_preference="prefer_unit"),
    ]
