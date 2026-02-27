"""
Module purpose:
- Define combat unit schemas and the default unit-card pool.

Type aliases:
- UnitClass: "unit" | "building" | "spell".
- AttackPreference: targeting preference strategy.
- TargetKind: target category returned by targeting logic.
- NearbyUnitStatus: role-adjacent unit health tag.

Data classes:
- UnitCard
  - name: card display name.
  - describe: free Chinese description.
  - attack: base attack value.
  - health: max health.
  - hit_speed: attack interval (smaller means faster).
  - move_speed: movement speed scalar.
  - consume: holy-water cost.
  - is_flying: whether the card is flying.
  - unit_class: card type.
  - attack_preference: target preference policy.
- DeployedUnit
  - unit_id: runtime unique id.
  - owner_name: player owner.
  - card: card schema.
  - current_health: runtime health.
  - node_name: spawn node.
  - is_wartime: True if deployed during battle phase.
  - deployed_time: world time when created.

Functions:
- build_default_unit_cards(): return default 8-card player pool.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

UnitClass = Literal["unit", "building", "spell"]
AttackPreference = Literal["prefer_unit", "prefer_building", "manual_spell"]
TargetKind = Literal["enemy_unit", "enemy_building", "enemy_npc", "field_building"]
NearbyUnitStatus = Literal["full", "damaged"]


@dataclass(frozen=True)
class UnitCard:
    name: str
    describe: str
    attack: float
    health: float
    hit_speed: float
    move_speed: float
    consume: float
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
        UnitCard(
            name="地狱飞龙",
            describe="高爆发空中单体输出，适合点杀高血目标。",
            attack=180,
            health=1100,
            hit_speed=1.6,
            move_speed=1.6,
            consume=4,
            is_flying=True,
            unit_class="unit",
            attack_preference="prefer_unit",
        ),
        UnitCard(
            name="电磁炮",
            describe="远程高伤建筑毁伤卡，提供稳定火力压制。",
            attack=320,
            health=1600,
            hit_speed=2.2,
            move_speed=0.8,
            consume=5,
            is_flying=False,
            unit_class="unit",
            attack_preference="prefer_unit",
        ),
        UnitCard(
            name="巨人",
            describe="高血前排，优先冲击敌方建筑。",
            attack=120,
            health=3500,
            hit_speed=1.5,
            move_speed=1.0,
            consume=5,
            is_flying=False,
            unit_class="unit",
            attack_preference="prefer_building",
        ),
        UnitCard(
            name="飓风法术",
            describe="可手动指定目标范围的控制类法术。",
            attack=40,
            health=1,
            hit_speed=1.0,
            move_speed=0.0,
            consume=3,
            is_flying=False,
            unit_class="spell",
            attack_preference="manual_spell",
        ),
        UnitCard(
            name="飞斧屠夫",
            describe="中速中高伤害地面单位，压制能力强。",
            attack=140,
            health=1000,
            hit_speed=1.3,
            move_speed=1.2,
            consume=4,
            is_flying=False,
            unit_class="unit",
            attack_preference="prefer_unit",
        ),
        UnitCard(
            name="骷髅军团",
            describe="人海战术单位，擅长包围与牵制。",
            attack=45,
            health=120,
            hit_speed=1.0,
            move_speed=1.8,
            consume=3,
            is_flying=False,
            unit_class="unit",
            attack_preference="prefer_unit",
        ),
        UnitCard(
            name="亡灵",
            describe="快速空中骚扰单位，机动性高。",
            attack=65,
            health=150,
            hit_speed=1.1,
            move_speed=1.9,
            consume=2,
            is_flying=True,
            unit_class="unit",
            attack_preference="prefer_unit",
        ),
        UnitCard(
            name="重甲亡灵",
            describe="耐久更高的空中突击单位。",
            attack=65,
            health=260,
            hit_speed=1.2,
            move_speed=1.7,
            consume=4,
            is_flying=True,
            unit_class="unit",
            attack_preference="prefer_unit",
        ),
    ]
