"""
Module purpose:
- Define static companion profile configuration.

Data model:
- CompanionProfile
  - name: companion name.
  - role_type: friendly | romance | event.
  - home_node: default resident node.
  - move_time_cost: movement cost applied to main player when this companion is in team.
  - can_attack: whether this companion has direct card combat ability.
  - deck: 8-card deck.
  - description: static story/behavior description.

Functions:
- build_default_companion_profiles(): build four default companions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CompanionRoleType = Literal["friendly", "romance", "event"]


@dataclass(frozen=True)
class CompanionProfile:
    name: str
    role_type: CompanionRoleType
    home_node: str
    move_time_cost: float
    can_attack: bool
    deck: list[str]
    description: str


def build_default_companion_profiles() -> dict[str, CompanionProfile]:
    """Build static companion profiles for current scenario."""

    return {
        "罗宾": CompanionProfile(
            name="罗宾",
            role_type="friendly",
            home_node="田径场",
            move_time_cost=1.5,
            can_attack=True,
            deck=["皮卡超人", "雷击法术", "电击法术", "万箭齐发", "飓风法术", "哥布林团伙", "火枪手", "加农炮"],
            description=(
                "常驻田径场跑步，友善角色，永远不会攻击主控玩家。"
                "注意到玩家后会主动提出加入队伍，与玩家共同战斗。"
                "加入队伍后对主角施加负重debuff，移动一条边耗时变为1.5。"
            ),
        ),
        "许琪琪": CompanionProfile(
            name="许琪琪",
            role_type="romance",
            home_node="东教学楼北",
            move_time_cost=2.0,
            can_attack=False,
            deck=["无战斗卡组", "无战斗卡组", "无战斗卡组", "无战斗卡组", "无战斗卡组", "无战斗卡组", "无战斗卡组", "无战斗卡组"],
            description=(
                "无战斗能力可攻略角色，常驻东教学楼北侧。"
                "只能在东教学楼内部往北侧的路上被发现；时间6到9因上厕所无法被发现。"
                "其余时刻可邀请加入，加入后随好感提升逐渐依赖主角。"
                "加入队伍后移动一条边耗时变为2。"
                "若被两名敌对角色注意到，会引发敌对角色吃醋愤怒。"
            ),
        ),
        "冬雨": CompanionProfile(
            name="冬雨",
            role_type="romance",
            home_node="图书馆",
            move_time_cost=1.5,
            can_attack=False,
            deck=["无卡组", "无卡组", "无卡组", "无卡组", "无卡组", "无卡组", "无卡组", "无卡组"],
            description=(
                "可攻略角色，常驻图书馆，任意时间在图书馆可被发现。"
                "提醒其校园事件会获得感激，可邀请加入队伍。"
                "性格沉稳，无卡牌能力，但加入后可帮助主角攻击靠近的近战单位。"
                "加入队伍后移动一条边耗时1.5。"
            ),
        ),
        "马超鹏": CompanionProfile(
            name="马超鹏",
            role_type="event",
            home_node="东教学楼内部",
            move_time_cost=1.0,
            can_attack=True,
            deck=["骷髅巨人", "女巫", "地狱飞龙", "火球", "亡灵大军", "骷髅墓碑", "掘地矿工", "骷髅军团"],
            description=(
                "事件角色。开局时间单位4以前可通过东教学楼事件加入队伍。"
                "加入后主角可使用其手机卡组进行战斗。"
            ),
        ),
    }
