"""
Module purpose:
- Define combat unit schemas and card libraries.

Type aliases:
- UnitClass: "unit" | "building" | "spell".
- AttackPreference: targeting preference strategy.
- TargetKind: target category returned by targeting logic.
- NearbyUnitStatus: role-adjacent unit health tag.
- HitSpeedTier: attack speed tier (high/mid/low).

Data classes:
- UnitCard
  - name: card display name.
  - describe: free Chinese description.
  - attack: 0-10 attack rating.
  - defense: 0-10 defense rating.
  - control: 0-10 control rating.
  - health: max health used by runtime unit instances.
  - hit_speed: high/mid/low.
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
- build_all_unit_cards(): return all known cards for player and NPC decks.
- build_default_unit_cards(): return the default 8-card player pool.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

UnitClass = Literal["unit", "building", "spell"]
AttackPreference = Literal["prefer_unit", "prefer_building", "manual_spell"]
TargetKind = Literal["enemy_unit", "enemy_building", "enemy_npc", "field_building"]
NearbyUnitStatus = Literal["full", "damaged"]
HitSpeedTier = Literal["high", "mid", "low"]


@dataclass(frozen=True)
class UnitCard:
    name: str
    describe: str
    attack: int
    defense: int
    control: int
    health: float
    hit_speed: HitSpeedTier
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


def _card(
    name: str,
    describe: str,
    attack: int,
    defense: int,
    control: int,
    health: float,
    hit_speed: HitSpeedTier,
    move_speed: float,
    consume: float,
    is_flying: bool,
    unit_class: UnitClass,
    attack_preference: AttackPreference,
) -> UnitCard:
    for v in (attack, defense, control):
        if v < 0 or v > 10:
            raise ValueError("attack/defense/control must be between 0 and 10.")
    return UnitCard(
        name=name,
        describe=describe,
        attack=attack,
        defense=defense,
        control=control,
        health=health,
        hit_speed=hit_speed,
        move_speed=move_speed,
        consume=consume,
        is_flying=is_flying,
        unit_class=unit_class,
        attack_preference=attack_preference,
    )


def build_all_unit_cards() -> list[UnitCard]:
    """All cards used by main player and static role decks."""

    return [
        _card("地狱飞龙", "高爆发空中单体输出。", 8, 5, 3, 1100, "mid", 1.6, 4, True, "unit", "prefer_unit"),
        _card("电磁炮", "远程压制卡，持续火力稳定。", 7, 6, 4, 1600, "low", 0.8, 5, False, "unit", "prefer_unit"),
        _card("巨人", "高耐久前排，优先拆建筑。", 5, 10, 2, 3500, "mid", 1.0, 5, False, "unit", "prefer_building"),
        _card("飓风法术", "位移控制法术，可手动定点。", 2, 1, 9, 1, "high", 0.0, 3, False, "spell", "manual_spell"),
        _card("飞斧屠夫", "中速中高伤害近战压制。", 7, 6, 3, 1000, "mid", 1.2, 4, False, "unit", "prefer_unit"),
        _card("骷髅军团", "人海牵制与包围。", 4, 2, 5, 120, "high", 1.8, 3, False, "unit", "prefer_unit"),
        _card("亡灵", "快速空中骚扰。", 5, 3, 4, 150, "high", 1.9, 2, True, "unit", "prefer_unit"),
        _card("重甲亡灵", "更高耐久的空中突击单位。", 5, 5, 4, 260, "mid", 1.7, 4, True, "unit", "prefer_unit"),
        _card("皮卡超人", "高额单体斩杀地面单位。", 10, 8, 2, 2800, "low", 0.9, 7, False, "unit", "prefer_unit"),
        _card("皇家幽灵", "潜行突袭，切后排能力强。", 7, 6, 5, 1200, "mid", 1.4, 3, False, "unit", "prefer_unit"),
        _card("神箭游侠", "远程穿透压线。", 8, 4, 6, 900, "mid", 1.0, 6, False, "unit", "prefer_unit"),
        _card("电击法术", "瞬时打断与清小怪。", 3, 1, 8, 1, "high", 0.0, 2, False, "spell", "manual_spell"),
        _card("幻影刺客", "高机动高爆发突袭单位。", 9, 5, 4, 1400, "mid", 1.5, 4, False, "unit", "prefer_unit"),
        _card("野蛮人攻城锤", "冲锋破点并展开压制。", 8, 6, 4, 1600, "mid", 1.6, 4, False, "unit", "prefer_building"),
        _card("火球", "稳定范围伤害与逼退。", 6, 1, 6, 1, "mid", 0.0, 4, False, "spell", "manual_spell"),
        _card("闪电法师", "群体电击控制与解场。", 6, 5, 7, 850, "mid", 1.2, 4, False, "unit", "prefer_unit"),
        _card("公主", "超远程消耗牵制。", 5, 2, 7, 500, "mid", 1.0, 3, False, "unit", "prefer_unit"),
        _card("复仇滚木", "地面直线清理与击退。", 4, 1, 7, 1, "high", 0.0, 2, False, "spell", "manual_spell"),
        _card("哥布林飞桶", "远投奇袭后排。", 6, 2, 6, 300, "mid", 1.3, 3, False, "unit", "prefer_unit"),
        _card("火箭", "超高伤害重型法术。", 10, 1, 5, 1, "low", 0.0, 6, False, "spell", "manual_spell"),
        _card("冰雪精灵", "低费冻结控制。", 2, 1, 8, 120, "high", 1.9, 1, False, "unit", "prefer_unit"),
        _card("哥布林团伙", "多单位协同压制。", 5, 3, 6, 400, "high", 1.8, 3, False, "unit", "prefer_unit"),
        _card("骷髅守卫", "护盾前排拖延推进。", 4, 5, 6, 700, "mid", 1.1, 3, False, "unit", "prefer_unit"),
        _card("地狱之塔", "反坦克防御核心建筑。", 9, 7, 3, 1800, "mid", 0.0, 5, False, "building", "prefer_unit"),
        _card("野猪骑士", "快速冲锋拆建筑。", 7, 5, 3, 1500, "high", 2.0, 4, False, "unit", "prefer_building"),
        _card("骷髅兵", "低费牵制与围攻。", 3, 1, 6, 90, "high", 2.0, 1, False, "unit", "prefer_unit"),
        _card("加农炮", "低费防守建筑。", 5, 6, 2, 1400, "mid", 0.0, 3, False, "building", "prefer_unit"),
        _card("火枪手", "稳定中远程输出。", 7, 4, 4, 850, "mid", 1.3, 4, False, "unit", "prefer_unit"),
        _card("戈伦冰人", "低费前排与减速骚扰。", 3, 7, 5, 1200, "low", 1.0, 2, False, "unit", "prefer_unit"),
    ]


def build_default_unit_cards() -> list[UnitCard]:
    """Default 8-card player pool."""

    default_names = [
        "地狱飞龙",
        "电磁炮",
        "巨人",
        "飓风法术",
        "飞斧屠夫",
        "骷髅军团",
        "亡灵",
        "重甲亡灵",
    ]
    library = {card.name: card for card in build_all_unit_cards()}
    return [library[name] for name in default_names]
