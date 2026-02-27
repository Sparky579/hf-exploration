"""
Module purpose:
- Provide static character profile storage for non-player roles.

Data model:
- CharacterProfile
  - name: character name.
  - alignment: role alignment (e.g., enemy/neutral).
  - description: static long-form behavior description.
  - status: "存活" or "死亡" (leaving campus is normalized to "死亡").
  - history: ordered operation history entries.
  - card_deck: fixed 8-card deck for this character.

Functions:
- build_default_character_profiles(): construct three predefined character profiles.
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
    """Build static profiles requested by the user."""

    return {
        "李再斌": CharacterProfile(
            name="李再斌",
            alignment="敌对角色",
            card_deck=[
                "皮卡超人",
                "皇家幽灵",
                "神箭游侠",
                "电击法术",
                "幻影刺客",
                "野蛮人攻城锤",
                "火球",
                "闪电法师",
            ],
            description=(
                "敌对角色，因感情受挫成为破坏狂，从宿舍出发。"
                "在不被干扰的时间线中：时间7下出皮卡超人，时间9摧毁宿舍；"
                "时间14到达国际部，时间15下出野蛮人攻城锤并摧毁国际部；"
                "之后沿东教学楼南、西教学楼南前往德政楼，总计7时间抵达；"
                "时间22下出幻影刺客，时间24再次下出幻影刺客并摧毁德政楼。"
                "该角色在未进行摧毁目标动作（赶路或静止）时，会注意同地点主控玩家，"
                "发现后会主动与主控玩家开启战斗状态。"
            ),
        ),
        "黎诺存": CharacterProfile(
            name="黎诺存",
            alignment="中立角色",
            card_deck=[
                "公主",
                "复仇滚木",
                "哥布林飞桶",
                "火箭",
                "冰雪精灵",
                "哥布林团伙",
                "骷髅守卫",
                "地狱之塔",
            ],
            description=(
                "致力于称霸校园。时间0开始停留在西教学楼南；时间8下出哥布林团伙向东移动；"
                "时间20下火箭远程瞄准颜宏帆并摧毁东教学楼；时间25到达图书馆并放下地狱之塔；"
                "时间27地狱之塔摧毁图书馆。该角色为中立，仅在被攻击其单位、被攻击本人、"
                "或对方主动宣战时才进入战斗。"
            ),
        ),
        "颜宏帆": CharacterProfile(
            name="颜宏帆",
            alignment="敌对角色",
            card_deck=[
                "野猪骑士",
                "骷髅兵",
                "加农炮",
                "火枪手",
                "冰雪精灵",
                "戈伦冰人",
                "火球",
                "复仇滚木",
            ],
            description=(
                "敌对角色，与黎诺存敌对。时间3在东教学楼内部放小骷髅扰乱课堂，随后立刻下楼到东教学楼南停留；"
                "时间9下野猪骑士向西教学楼，时间11野猪拆掉西教学楼；时间19下火枪手；"
                "时间20该角色与其全部单位及东教学楼被火箭摧毁（若黎诺存被干扰未能放火箭则继续停留原地）。"
                "若其看到主控玩家与许琪琪同处，会无视其他状态愤怒并进入对玩家敌对。"
            ),
        ),
    }
