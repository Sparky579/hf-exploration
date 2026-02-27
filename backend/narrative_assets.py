"""
Module purpose:
- Store narrative-facing static assets used by LLM prompts: world base setting text,
  per-scene descriptive paragraphs, and role-to-scene association metadata.

Functions:
- build_world_base_setting(): return long-form base setting text of 向西中学.
- get_scene_paragraph(node_name): return one scene paragraph by node name.
- list_scene_paragraphs(): return all scene paragraphs.
- get_role_associated_nodes(role_name): return the scene nodes associated with one role.
- roles_related_to_node(node_name): return role names associated with one scene node.
"""

from __future__ import annotations

WORLD_BASE_SETTING = (
    "这里是向西中学，原本是一座充满青春气息的校园。教学楼、宿舍、图书馆、体育馆、食堂、田径场，以及厚重的前后门，构成了这个仿佛被诅咒的封闭舞台。"
    "时间成了最致命的量度，每一次在阴影中的潜行与亡命狂奔都将榨干你的精力。唯有那泛着诡异紫光的神秘液体——「圣水」，是你在这疯狂世道里生存、乃至反杀的唯一筹码。"
    "刺耳的警报将不期而至，崩塌的楼宇随处可见，还有随时可能将所有人吞噬的倒计时爆炸。在这个化作炼狱的学校里，各怀鬼胎的角色们正有条不紊地推进着他们的破坏计划；"
    "但别绝望，总有战友潜伏在黑暗角落等你发现，邀请他们入队，不仅能为你抵挡致命的威胁，更将重写你的命运卡组与结局。"
)

SCENE_PARAGRAPHS: dict[str, str] = {
    "正门": "雄伟的正门外是通向自由最宽阔的大道。阳光毫无遮掩地洒在路面上，却让你像个显眼的活靶子，任何嗜血的猎手都能第一眼锁定你慌乱的背影。",
    "国际部": "充满现代气息的国际部是关键的逃生暗门。在秩序尚未彻底崩解前，它是你的诺亚方舟；但只要它在战火中化作废墟，你这唯一的希望便会与其一同埋葬。",
    "东教学楼南": "人头攒动的东侧南廊，平时热闹非凡，如今却是暗流涌动的高危浅滩。当狂乱与恐慌如瘟疫般蔓延，最惨烈的踩踏与杀戮往往在这里拉开帷幕。",
    "南教学楼": "像一条脊椎般连接着校园中轴，它是你绝佳的转移掩体。但在那深邃的走廊里，如果两头的出口被同时封锁，这里就是一块插翅难飞的铁板烧。",
    "西教学楼南": "紧邻着散发书墨香的图书馆与汗水挥洒的体育馆，这里的空气总是微妙的凝滞——总有些冷酷的观望者潜伏于此，像秃鹫般静候着两败俱伤的残局。",
    "德政楼": "象征着校园最高权力的德政楼，如今化作了灾难的心脏。只要那巍峨的轮廓轰然崩塌，死神的沙漏便会冷酷地倒转，将所有人锁死在绝望的高压倒数中，无一幸免。",
    "宿舍": "曾是你最温暖的避风港，如今那逼仄狭长的楼道却成了致命的迷宫。哪怕只是一次不痛不痒的爆炸产生的碎石，都可能将你唯一的退路彻底堵死。",
    "东教学楼内部": "伴随着刺鼻的粉笔灰和数学老师催眠般的讲课声，这里是一切梦魇开始的地方。当你低头点亮屏幕的那一瞬，命运的齿轮已悄然咬合，你的同伴与底牌就此注定。",
    "图书馆": "一排排沉寂的书架在这无序的疯狂中显得荒诞又诡异。它既可能是你喘息待发的最后堡垒，也极易成为疯子们肆意倾泻火力的绝佳焚化炉。",
    "小卖部": "原本充满欢声笑语和零食香气的转角小店，现在却成了连接食堂、北侧冰冷暗道和开阔田径场的兵家必争之地。跨过这里，步步杀机。",
    "东教学楼北": "终年不见阳光的北侧小道，隐蔽得连疯子都懒得多看一眼。也许那个名叫许琪琪、瑟瑟发抖的女孩，正缩在某个生满青苔的角落里绝望地祈求救援。",
    "生化楼": "空气中永远发酵着淡淡的福尔马林味。它像一颗钉子死死扎在中段，向前可切入充满未知的西北死角，向后则能仓皇退守宽阔的田径场。",
    "西教学楼北": "刺耳的法术爆炸和嘶吼声在这条通道上反复回荡。作为切入体育馆咽喉的必经血路，不知道有多少不自量力的单位在这里化为了碎光和齑粉。",
    "体育馆": "空旷得连呼吸都有回音的钢铁巨兽。光洁的地板毫无躲闪的余地，虽能让重型法术无差别洗地，但停留在这是将自己的命挂在敌人的准星上。",
    "食堂": "踩在油腻打滑的瓷砖上，向后直通生路微茫的后门。当身后的追兵如同附骨之疽般逼近时，你只能死咬着牙，在这条最容易滑倒的血路上狂奔。",
    "田径场": "平日洋溢着青春荷尔蒙的绿茵场，此刻犹如残酷古罗马角斗场。罗宾依然坚持在那红色的塑胶跑道上巡跑，这里视野开阔，适合集结，更适合大开杀戒。",
    "后门": "那扇铁锈斑斑的门扉，是末日收割前最后撕开的一道缝隙。当全校坠入毁灭的深渊，疯狂倒计时敲响时，它将是你沾满鲜血的双手能够死死抓住的最后一根救命稻草。",
}

ROLE_ASSOCIATED_NODES: dict[str, list[str]] = {
    "李再斌": ["宿舍", "国际部", "东教学楼南", "西教学楼南", "德政楼"],
    "黎诺存": ["西教学楼南", "图书馆", "东教学楼南"],
    "颜宏帆": ["东教学楼内部", "东教学楼南", "西教学楼南"],
    "罗宾": ["田径场"],
    "许琪琪": ["东教学楼内部", "东教学楼北"],
    "冬雨": ["图书馆"],
    "马超鹏": ["东教学楼内部"],
}


def build_world_base_setting() -> str:
    """Return the base world setting text used in LLM prompts."""

    return WORLD_BASE_SETTING


def get_scene_paragraph(node_name: str) -> str:
    """Return a scene paragraph by node name."""

    return SCENE_PARAGRAPHS.get(node_name, "该地点暂无预置叙事描述。")


def list_scene_paragraphs() -> dict[str, str]:
    """Return all configured scene paragraphs."""

    return dict(SCENE_PARAGRAPHS)


def get_role_associated_nodes(role_name: str) -> list[str]:
    """Return associated nodes of one role."""

    return list(ROLE_ASSOCIATED_NODES.get(role_name, []))


def roles_related_to_node(node_name: str) -> list[str]:
    """Return all role names that are associated with one node."""

    hits: list[str] = []
    for role_name, nodes in ROLE_ASSOCIATED_NODES.items():
        if node_name in nodes:
            hits.append(role_name)
    return hits
