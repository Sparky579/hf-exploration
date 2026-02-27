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
    "舞台是向西中学。校园区域包含教学楼、宿舍、图书馆、体育馆、食堂、田径场与前后门。"
    "玩家以时间单位驱动行动，移动遵循地图邻接边，核心资源是圣水。"
    "故事中存在警报、紧急与爆炸等全局触发事件；部分角色会按时间轴推进破坏行动，"
    "部分角色可被发现并邀请入队，进而影响移动耗时、卡组与剧情分支。"
)

SCENE_PARAGRAPHS: dict[str, str] = {
    "正门": "正门外是最直观的逃离路线，视野开阔但也最容易被敌对角色发现。",
    "国际部": "国际部是关键事件出口，局势稳定时可撤离，若被摧毁则撤离选项会消失。",
    "东教学楼南": "东教学楼南是人流密集通道，冲突往往在这里首次显形。",
    "南教学楼": "南教学楼连接中轴，适合转移但也容易被夹击。",
    "西教学楼南": "西教学楼南靠近图书馆与体育馆分支，常出现中立角色的观望对峙。",
    "德政楼": "德政楼是紧急阶段触发核心点，一旦被摧毁将进入高压倒计时。",
    "宿舍": "宿舍区道路狭窄，破坏事件容易造成路线封锁。",
    "东教学楼内部": "东教学楼内部是开场课堂事件中心，早期分支选择会在此决定后续卡组与队友。",
    "图书馆": "图书馆相对安静，但也可能在中后期成为防守据点或被重点摧毁目标。",
    "小卖部": "小卖部是中转节点，连接食堂、教学楼北侧与田径场路线。",
    "东教学楼北": "东教学楼北路径隐蔽，许琪琪相关发现事件主要发生在这里。",
    "生化楼": "生化楼位于中段，既能转向西北通道，也能回撤到田径场。",
    "西教学楼北": "西教学楼北常见单位交火，是从中路切向体育馆的重要连接位。",
    "体育馆": "体育馆空间大、掩体少，适合拉开战线但不适合长期停留。",
    "食堂": "食堂附近路线直通后门，是被追击时的高风险撤离通道。",
    "田径场": "田径场地形开阔，罗宾常驻此地，适合会合但容易暴露行踪。",
    "后门": "后门是后期高价值撤离点，紧急阶段常成为最后生路。",
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
