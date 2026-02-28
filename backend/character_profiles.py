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
                "已被彻底吞噬的疯狂破坏者。他的眼中抹平了同学的界线，只剩下纯粹的毁灭欲——将这座校园化作瓦砾是他唯一的盛宴。"
                "与你那可怜的挣扎相比，他更迷恋大楼在法术中轰然倒塌的美妙巨响。"
                "固定诡秘轨迹（若无阻碍）：清晨从宿舍破茧而出，t=7释放皮卡超人，t=9将宿舍粉碎成泥；"
                "随后踏着废墟于t=14逼近国际部，t=15架起野蛮人攻城锤将希望之门摧残殆尽；"
                "接着如死神过境般碾过东教学楼南、西教学楼南，耗时7刻直指德政楼；t=22挥出幻影刺客的鬼魅一击，t=24补上致命一击让权力中枢随风消散。"
                "惊悚连结：若在他漫无目的或寻觅猎物的路上（无拆楼目标）遇到了你，残暴的猎杀本能会立刻将你标记为第一死敌；"
                "但若是你趁他沉醉于撕裂钢筋水泥的病态狂欢时与之撞见，只需不激怒他，这头怪物甚至连多看你一眼的闲暇都没有。"
            ),
        ),
        "黎诺存": CharacterProfile(
            name="黎诺存",
            alignment="中立角色",
            card_deck=["公主", "复仇滚木", "哥布林飞桶", "火箭", "冰雪精灵", "哥布林团伙", "骷髅守卫", "地狱之塔"],
            description=(
                "如寒冰般冷酷的棋手。他不在乎灾难本身，只是渴望在这片血海里重新树立那令人战栗的残酷「秩序」。"
                "他的字典里没有无意义的暴行，更没把你当回事儿——前提是，你别不知好歹地越过他划下的红线。"
                "冷血行动律（若无阻碍）：t=0起他便如石像般静默于西教学楼南的阴影中；t=8指派哥布林团伙向东残忍压制幸存者；"
                "t=20准时向心怀怨恨的宿敌颜宏帆射出毁灭火箭，连带将整栋东教学楼抹去；t=25幽灵般飘至图书馆布下高亢燃烧的地狱之塔，t=27将千万册藏书化为火海。"
                "冰冷威慑律：平时遭遇你只会惹来他轻蔑的冷眼端详；他绝不轻易动用底牌，"
                "除非你愚蠢到将战火烧到了他或他在乎的一切头上。一旦遭到挑衅，迎接你的将是压倒性的精确制裁。"
            ),
        ),
        "颜宏帆": CharacterProfile(
            name="颜宏帆",
            alignment="敌对角色",
            card_deck=["野猪骑士", "骷髅兵", "加农炮", "火枪手", "冰雪精灵", "戈伦冰人", "火球", "复仇滚木"],
            description=(
                "这是一颗随时会爆炸的活体炸药，与黎诺存之间隔着万丈仇渊，他的理性之弦早已崩断。毫无征兆的恶作剧才是他病态享受的开始。"
                "狂热剧本（若无阻碍）：t=3准时于压抑的东教学楼课堂中趁人不备偷偷放出一只令人毛骨悚然的小骷髅，随后趁着大家没反应过来悄悄溜出门外，在同学们的尖叫声中悠哉地躲到南面落脚；"
                "t=9毫不留情地指挥野猪骑士狂躁地冲向西教学楼，t=11即将其夷为平地；t=19下出火枪手；"
                "到了t=20，若黎诺存那发火箭真如约砸下，他将带着他所有的造物和东教学楼一起灰飞烟灭；若没落下，他则继续冷笑存活。"
                "嫉妒之核：他那畸形的占有欲无时无刻不在作祟，一旦撞见你和柔弱的许琪琪纠缠不清，脑海中某种扭曲的嫉妒便会彻底爆裂——"
                "此时所有的建筑都不再重要，他会像疯狗一样红着眼只求将你撕得粉碎。"
            ),
        ),
        "罗宾": CharacterProfile(
            name="罗宾",
            alignment="友善角色",
            card_deck=["皮卡超人", "雷击法术", "电击法术", "万箭齐发", "飓风法术", "哥布林团伙", "火枪手", "加农炮"],
            description=(
                "那个仿佛永远在田径场挥洒汗水的老实人，哪怕在末日降临时也因为过分温和而显得有些钝感。"
                "不离不弃：当你带着满身硝烟跌撞至他面前时，他会先憨厚而警惕地观察你的状态。"
                "确认你没疯后，他甚至不需太多言语便主动作出承诺：“交给我。”"
                "自他入队的那一刻起，他和他的部队将永远挡在最前线——没有指责，没有废话，只有在你最绝望的时机，不遗余力地砸下最狂暴的法术支援。"
            ),
        ),
        "许琪琪": CharacterProfile(
            name="许琪琪",
            alignment="可攻略角色",
            card_deck=["无战斗卡组", "无战斗卡组", "无战斗卡组", "无战斗卡组", "无战斗卡组", "无战斗卡组", "无战斗卡组", "无战斗卡组"],
            description=(
                "一只惊恐到连指尖都在发颤的瓷娃娃。她不具备半点战斗天赋，平日最喜欢将自己藏身在东教学楼北侧那阴冷鲜为人知的缝隙里。"
                "命运交汇：若你能如天神般降临在她面前，"
                "她会不顾一切地抓住你这最后的救命稻草。随着好感的剧烈升温，她会深中名叫依赖的毒药，一次次用带有哭腔的只言片语向你渴求安全感。"
                "致命魅力：红颜往往伴随祸水，她那无端惹人怜爱的脆弱，极易激燃其他病态疯子心中扭曲的占有欲；"
                "这使得你必须在多方势力的妒火与血战中，用命替她杀出重围。"
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
                "机敏异常，在天崩地裂前，他是你在东教学楼内最宝贵的一粒骰子。"
                "患难见真情：在t=4之前，你随时都有机会通过突发事件将这个眼力极好的家伙拉下水。"
                "哪怕他因为慷慨借你热点而被老师当场逮住，只要课堂的大门在尖叫中崩穿，"
                "他绝不会怪你连累了他；相反，他会毫不犹豫地将那支藏有逆天卡组的手机交给你——"
                "“别废话，拿着上！”在那生死交织的一瞬间，你代替了他的意志，接管了他的杀器，正式踏入这深渊的残酷牌局。"
                "（重要注意：因为马超鹏把备用手机直接交给了主控玩家，所以即使他后续入队，他自身的圣水永远是 0，永远无法主动下牌。他的卡组变成了主控玩家的专属卡组。）"
            ),
        ),
    }
