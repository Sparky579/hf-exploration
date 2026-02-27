"""
Module purpose:
- Provide static character profile storage for scenario roles.

Data model:
- CharacterProfile
  - name: character name.
  - alignment: role alignment (enemy/neutral/friendly/romance/event).
  - description: static long-form behavior description including reaction rules.
  - status: "存活" or "死亡" (leaving campus is normalized to "死亡").
  - history: ordered operation history entries.
  - card_deck: fixed 8-card deck.

Functions:
- build_default_character_profiles(): construct predefined role profiles with detailed reactions.
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
                "敌对角色。情绪失控后将摧毁校园设施当作宣泄手段，行动目标高度明确，优先执行“破坏建筑”而不是与旁人缠斗。"
                "固定轨迹（无人干扰）为：宿舍出发，t=7下皮卡超人，t=9摧毁宿舍；t=14到国际部，t=15下野蛮人攻城锤并摧毁国际部；"
                "随后沿东教学楼南→西教学楼南→德政楼推进，共7时间单位到达德政楼；t=22下幻影刺客，t=24再次下幻影刺客并摧毁德政楼。"
                "反应规则：在“赶路/待机且无当前拆楼目标”阶段，会观察同地点主控玩家，一旦发现即主动进入敌对战斗状态；"
                "若正处于拆楼动作中，则短时忽略挑衅，优先完成当前破坏动作。"
            ),
        ),
        "黎诺存": CharacterProfile(
            name="黎诺存",
            alignment="中立角色",
            card_deck=["公主", "复仇滚木", "哥布林飞桶", "火箭", "冰雪精灵", "哥布林团伙", "骷髅守卫", "地狱之塔"],
            description=(
                "中立角色，目标是“控制局势并维持威慑”，更偏理性，不会主动把主控玩家当敌人。"
                "固定轨迹（无人干扰）为：t=0起常驻西教学楼南；t=8下哥布林团伙向东压制；t=20下火箭远程瞄准颜宏帆并摧毁东教学楼；"
                "t=25到图书馆并下地狱之塔，t=27地狱塔摧毁图书馆。"
                "反应规则：仅在“被攻击其本人/其单位”或“被主控明确宣战”时转入战斗；"
                "若只是同场景遭遇，会保持观望与试探，不先手。"
            ),
        ),
        "颜宏帆": CharacterProfile(
            name="颜宏帆",
            alignment="敌对角色",
            card_deck=["野猪骑士", "骷髅兵", "加农炮", "火枪手", "冰雪精灵", "戈伦冰人", "火球", "复仇滚木"],
            description=(
                "敌对角色，与黎诺存互相仇视。行动风格偏冲动，容易被情绪触发。"
                "固定轨迹（无人干扰）为：t=3在东教学楼内部放小骷髅扰乱课堂，随后下楼至东教学楼南停留；"
                "t=9下野猪骑士向西教学楼推进，t=11野猪摧毁西教学楼；t=19下火枪手；"
                "t=20若黎诺存成功放火箭，则其本人、其全部单位及东教学楼被一并摧毁；若火箭未发出则继续原地存活。"
                "反应规则：若观察到主控玩家与许琪琪同处，会立刻进入“吃醋愤怒”状态并强制敌对，优先追击主控。"
            ),
        ),
        "罗宾": CharacterProfile(
            name="罗宾",
            alignment="友善角色",
            card_deck=["皮卡超人", "雷击法术", "电击法术", "万箭齐发", "飓风法术", "哥布林团伙", "火枪手", "加农炮"],
            description=(
                "友善角色，常驻田径场跑步。性格温和、反应略慢，平时话不多；"
                "刚发现主控时会先确认对方状态，再主动提出加入队伍。"
                "反应规则：永远不会攻击主控；加入后优先跟随主控位置与战斗节奏，"
                "在未进入高压战斗时通常保持沉默观察。"
            ),
        ),
        "许琪琪": CharacterProfile(
            name="许琪琪",
            alignment="可攻略角色",
            card_deck=["无战斗卡组", "无战斗卡组", "无战斗卡组", "无战斗卡组", "无战斗卡组", "无战斗卡组", "无战斗卡组", "无战斗卡组"],
            description=(
                "可攻略角色，无卡牌战斗能力。常驻东教学楼北侧，仅能在东教学楼内部通往北侧的路径上被发现。"
                "时间6~9因上厕所暂不可发现，其余时段可邀请入队。性格柔弱，存在感强，随好感增加会逐步依赖主控。"
                "反应规则：若被两名敌对角色同时注意，会触发敌对角色吃醋愤怒；"
                "加入后会在对话里更频繁寻求安全确认。"
            ),
        ),
        "冬雨": CharacterProfile(
            name="冬雨",
            alignment="可攻略角色",
            card_deck=["无卡组", "无卡组", "无卡组", "无卡组", "无卡组", "无卡组", "无卡组", "无卡组"],
            description=(
                "可攻略角色，常驻图书馆，全时段可发现。性格沉稳，沟通克制但关键时刻会主动补位。"
                "虽无出牌能力，但加入后可协助主控拦截靠近的近战单位。"
                "反应规则：初见若主控先提醒校园危机，会显著提升信任与好感；"
                "在多角色同场时，会优先给出冷静、可执行建议。"
            ),
        ),
        "马超鹏": CharacterProfile(
            name="马超鹏",
            alignment="事件角色",
            card_deck=["骷髅巨人", "女巫", "地狱飞龙", "火球", "亡灵大军", "骷髅墓碑", "掘地矿工", "骷髅军团"],
            description=(
                "事件角色，机敏，擅长快速判断风险。默认在东教学楼内部相关事件中出现，时间单位4以前可被事件拉入队伍。"
                "加入后主控改用其手机卡组战斗。"
                "反应规则：若事件中被老师收手机会短时失去行动，但在课堂崩坏后仍可能把手机交给主控继续推进。"
            ),
        ),
    }
