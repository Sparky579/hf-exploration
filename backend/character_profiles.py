"""
Module purpose:
- Provide static character profile storage for scenario roles.

Data model:
- CharacterProfile
  - name: character name.
  - alignment: role alignment (enemy/neutral/friendly/romance/event).
  - description: static long-form behavior description.
  - status: "存活" or "死亡" (leaving campus is normalized to "死亡").
  - history: ordered operation history entries.
  - card_deck: fixed 8-card deck.

Functions:
- build_default_character_profiles(): construct predefined role profiles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

CharacterStatus = Literal["存活", "死亡"]


@dataclass
class CharacterProfile:
    name: str
    alignment: str
    description: str
    status: CharacterStatus = "存活"
    history: list[str] = field(default_factory=list)
    card_deck: list[str] = field(default_factory=list)

    def set_status(self, status: str) -> None:
        normalized = status.strip()
        if normalized in ("离开校园", "离开", "已离校"):
            self.status = "死亡"
            self.history.append("状态变更：离开校园，按规则记为死亡。")
            return
        if normalized not in ("存活", "死亡"):
            raise ValueError("status must be one of: 存活, 死亡, 离开校园")
        self.status = normalized  # type: ignore[assignment]

    def add_history(self, text: str) -> None:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("history text must be non-empty.")
        self.history.append(text)

    def remove_history(self, text: str) -> None:
        if text in self.history:
            self.history.remove(text)

    def set_card_deck(self, deck: list[str]) -> None:
        if len(deck) != 8:
            raise ValueError("character card_deck must contain exactly 8 cards.")
        self.card_deck = list(deck)


def build_default_character_profiles() -> dict[str, CharacterProfile]:
    """Build static profiles requested by user stories."""

    return {
        "李再斌": CharacterProfile(
            name="李再斌",
            alignment="敌对角色",
            card_deck=["皮卡超人", "皇家幽灵", "神箭游侠", "电击法术", "幻影刺客", "野蛮人攻城锤", "火球", "闪电法师"],
            description=(
                "敌对角色，因感情受挫成为破坏狂，从宿舍出发。"
                "不受干扰时间线：时间7下皮卡超人，时间9摧毁宿舍；时间14到国际部，时间15下野蛮人攻城锤并摧毁国际部；"
                "随后途经东教学楼南、西教学楼南并花费7时间抵达德政楼；时间22下幻影刺客，时间24再下幻影刺客并摧毁德政楼。"
                "无摧毁目标时会观察同地点主控玩家，发现后主动进入战斗状态。"
            ),
        ),
        "黎诺存": CharacterProfile(
            name="黎诺存",
            alignment="中立角色",
            card_deck=["公主", "复仇滚木", "哥布林飞桶", "火箭", "冰雪精灵", "哥布林团伙", "骷髅守卫", "地狱之塔"],
            description=(
                "致力于称霸校园。时间0起停留西教学楼南；时间8下哥布林团伙向东移动；"
                "时间20下火箭远程瞄准颜宏帆并摧毁东教学楼；时间25到图书馆并下地狱之塔；时间27地狱之塔摧毁图书馆。"
                "中立，仅在被攻击单位/本人或对方宣战时进入战斗。"
            ),
        ),
        "颜宏帆": CharacterProfile(
            name="颜宏帆",
            alignment="敌对角色",
            card_deck=["野猪骑士", "骷髅兵", "加农炮", "火枪手", "冰雪精灵", "戈伦冰人", "火球", "复仇滚木"],
            description=(
                "敌对角色，与黎诺存敌对。时间3在东教学楼内部放小骷髅扰乱课堂，随后下楼到东教学楼南停留；"
                "时间9下野猪骑士向西教学楼；时间11野猪拆掉西教学楼；时间19下火枪手；"
                "时间20被火箭摧毁（若黎诺存受干扰未放火箭则留在原地）。"
                "若看到主控玩家与许琪琪同处，会无视其他状态并进入敌对。"
            ),
        ),
        "罗宾": CharacterProfile(
            name="罗宾",
            alignment="友善角色",
            card_deck=["皮卡超人", "雷击法术", "电击法术", "万箭齐发", "飓风法术", "哥布林团伙", "火枪手", "加农炮"],
            description="常驻田径场跑步，注意到玩家后主动提议加入队伍，且永远不会攻击主控玩家。",
        ),
        "许琪琪": CharacterProfile(
            name="许琪琪",
            alignment="可攻略角色",
            card_deck=["无战斗卡组", "无战斗卡组", "无战斗卡组", "无战斗卡组", "无战斗卡组", "无战斗卡组", "无战斗卡组", "无战斗卡组"],
            description=(
                "无战斗能力可攻略角色，常驻东教学楼北侧。"
                "仅在东教学楼内部往北路径可被发现；时间6到9不可发现。可邀请加入队伍。"
            ),
        ),
        "冬雨": CharacterProfile(
            name="冬雨",
            alignment="可攻略角色",
            card_deck=["无卡组", "无卡组", "无卡组", "无卡组", "无卡组", "无卡组", "无卡组", "无卡组"],
            description="可攻略角色，常驻图书馆，可被邀请入队，加入后可协助攻击近战目标。",
        ),
        "马超鹏": CharacterProfile(
            name="马超鹏",
            alignment="事件角色",
            card_deck=["骷髅巨人", "女巫", "地狱飞龙", "火球", "亡灵大军", "骷髅墓碑", "掘地矿工", "骷髅军团"],
            description="时间单位4以前可通过东教学楼事件加入，加入后主角可使用其手机卡组作战。",
        ),
    }
