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
    control: int,
    health: float,
    hit_speed: HitSpeedTier,
    move_speed: float,
    consume: float,
    is_flying: bool,
    unit_class: UnitClass,
    attack_preference: AttackPreference,
) -> UnitCard:
    for v in (attack, control):
        if v < 0 or v > 10:
            raise ValueError("attack/control must be between 0 and 10.")
    return UnitCard(
        name=name,
        describe=describe,
        attack=attack,
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
        _card("地狱飞龙", "高爆发空中单体输出。对同一个单位伤害会随着时间指数增长(从2到10)。", 2, 3, 5, "mid", 1.6, 4, True, "unit", "prefer_unit"),
        _card("电磁炮", "远程对地面AOE压制卡，爆发火力高。需要2单位时间充能，电类单位可以打断充能。", 8, 4, 6, "very_low", 0.8, 6, False, "unit", "prefer_unit"),
        _card("巨人", "高耐久前排，优先拆建筑。被人海克制。", 4, 2, 14, "mid", 1.0, 5, False, "unit", "prefer_building"),
        _card("飓风法术", "位移控制聚怪法术，有少量伤害，可手动定点。", 1, 9, 0, "high", 0.0, 3, False, "spell", "manual_spell"),
        _card("飞斧屠夫", "中速中高伤害AOE近战压制。", 4, 3, 4, "mid", 1.2, 5, False, "unit", "prefer_unit"),
        _card("骷髅军团", "十几只骷髅，人海牵制与包围，若没有被快速解决会造成海量伤害。", 8, 5, 1, "high", 1.8, 3, False, "unit", "prefer_unit"),
        _card("亡灵", "3只小型空中单位，快速骚扰。", 4, 4, 2, "high", 1.9, 3, True, "unit", "prefer_unit"),
        _card("重甲亡灵", "一只更高耐久的空中突击单位。", 3, 4, 3, "mid", 1.7, 3, True, "unit", "prefer_unit"),
        _card("皮卡超人", "高额单体斩杀地面单位。被人海克制。", 8, 2, 13, "low", 0.9, 7, False, "unit", "prefer_unit"),
        _card("皇家幽灵", "潜行AOE突袭，切后排能力强。", 7, 5, 1200, "mid", 1.4, 3, False, "unit", "prefer_unit"),
        _card("神箭游侠", "远程AOE穿透压线。", 8, 6, 3, "mid", 1.0, 3, False, "unit", "prefer_unit"),
        _card("电击法术", "瞬时打断与清小怪。", 1, 8, 0, "high", 0.0, 2, False, "spell", "manual_spell"),
        _card("幻影刺客", "高机动高爆发突袭单体伤害单位。", 9, 4, 5, "mid", 1.5, 3, False, "unit", "prefer_unit"),
        _card("野蛮人攻城锤", "冲锋破点并展开压制，撞到建筑或者被攻击后变成两只普通野蛮人。", 8, 4, 5, "mid", 1.6, 4, False, "unit", "prefer_building"),
        _card("火球", "稳定范围伤害与逼退。", 6, 6, 1, "mid", 0.0, 4, False, "spell", "manual_spell"),
        _card("闪电法师", "群体电击控制与解场。入场时释放带有1点伤害的电击法术。", 3, 7, 3, "mid", 1.2, 4, False, "unit", "prefer_unit"),
        _card("公主", "超远程低伤害AOE，消耗牵制。", 1, 7, 2, "mid", 1.0, 3, False, "unit", "prefer_unit"),
        _card("复仇滚木", "地面直线清理与击退。", 2, 7, 1, "high", 0.0, 2, False, "spell", "manual_spell"),
        _card("哥布林飞桶", "本身没有伤害，但远投三只哥布林奇袭后排。", 4, 6, 1, "mid", 1.3, 3, False, "unit", "prefer_unit"),
        _card("火箭", "超高伤害重型法术，有1单位的延迟。", 10, 5, 1, "low", 0.0, 6, False, "spell", "manual_spell"),
        _card("冰雪精灵", "低费冻结控制，自杀式攻击，冻完即死。", 1, 8, 2, "high", 1.9, 1, False, "unit", "prefer_unit"),
        _card("哥布林团伙", "人海，6只近战+远程投矛哥布林多单位协同压制。", 6, 6, 1, "high", 1.8, 3, False, "unit", "prefer_unit"),
        _card("骷髅守卫", "3只持盾骷髅，前排拖延推进。有一个绝对防御护盾，能绝对免疫第一次受到伤害。", 3, 6, 2, "mid", 1.1, 3, False, "unit", "prefer_unit"),
        _card("地狱之塔", "反坦克防御核心建筑，单体伤害被人海克制，对单伤害从2到10指数增长。", 2, 3, 7, "mid", 0.0, 5, False, "building", "prefer_unit"),
        _card("野猪骑士", "快速冲锋拆建筑。", 4, 3, 6, "high", 2.0, 4, False, "unit", "prefer_building"),
        _card("骷髅兵", "3只骷髅，低费牵制，只是看起来可怕，身板非常脆弱。", 3, 6, 1, "high", 2.0, 1, False, "unit", "prefer_unit"),
        _card("加农炮", "低费防守建筑。", 2, 2, 4, "mid", 0.0, 3, False, "building", "prefer_unit"),
        _card("火枪手", "稳定中远程输出。", 4, 4, 4, "mid", 1.3, 4, False, "unit", "prefer_unit"),
        _card("戈伦冰人", "低费前排与减速骚扰，死亡后减速周围敌人并造成1点伤害。", 1, 5, 5, "low", 1.0, 2, False, "unit", "prefer_unit"),
        _card("雷击法术", "高额法术斩杀与打断，攻击范围内最多3个单位，无法针对人海。", 7, 6, 1, "low", 0.0, 6, False, "spell", "manual_spell"),
        _card("万箭齐发", "大范围清场法术。", 2, 7, 1, "mid", 0.0, 3, False, "spell", "manual_spell"),
        _card("骷髅巨人", "高血量低伤害，死亡后留下巨大炸弹，1单位后爆炸，威力能炸毁一栋楼。", 7, 9, 3000, "low", 0.9, 6, False, "unit", "prefer_building"),
        _card("女巫", "召唤系远程AOE单位，每个时间单位召唤3只骷髅（一队骷髅兵）。", 1, 7, 7, "mid", 1.1, 5, False, "unit", "prefer_unit"),
        _card("亡灵大军", "空中人海，群体压制，若没有被快速解决会造成海量伤害，被万箭齐发克制。", 4, 7, 2, "high", 1.8, 5, True, "unit", "prefer_unit"),
        _card("骷髅墓碑", "拖延与召唤防守建筑，每个时间单位召唤3只小骷髅（一队骷髅兵），本体被击毁再召唤3只。", 2, 8, 4, "low", 0.0, 3, False, "building", "prefer_unit"),
        _card("掘地矿工", "可以随意挖掘到任意角落，定点突袭后排单位。", 2, 6, 5, "high", 1.7, 3, False, "unit", "prefer_unit"),
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

