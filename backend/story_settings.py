"""
Module purpose:
- Provide static global story settings, built-in trigger thresholds, and opening scripted trigger texts.

Data model:
- GlobalStorySetting
  - title: story title.
  - story_text: full narrative text.
  - alert_trigger_time: school alert trigger threshold (`time > threshold`).
  - emergency_blast_delay: explosion delay after emergency starts.
  - escape_nodes_before_alert: allowed escape nodes before alert.
  - escape_nodes_during_emergency: allowed escape nodes during emergency window.
  - opening_trigger_texts: scripted trigger sentences loaded into runtime at game start.

Functions:
- build_default_story_setting(): construct default story setting and opening trigger texts.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GlobalStorySetting:
    title: str
    story_text: str
    alert_trigger_time: float = 8.0
    emergency_blast_delay: float = 6.0
    escape_nodes_before_alert: set[str] = field(default_factory=lambda: {"正门", "后门", "国际部"})
    escape_nodes_during_emergency: set[str] = field(default_factory=lambda: {"正门", "后门", "国际部"})
    opening_trigger_texts: list[str] = field(default_factory=list)


def build_default_story_setting() -> GlobalStorySetting:
    """Build default global story setting."""

    return GlobalStorySetting(
        title="向西中学校园危机",
        story_text=(
            "时间8后校园进入警报状态。警报前玩家可从正门、后门、国际部逃离；警报后常规逃离通道关闭。"
            "若德政楼被摧毁，则进入紧急状态并启动6时间单位后的学校爆炸倒计时；"
            "紧急窗口中结界消失，可再次通过指定出口尝试逃离。"
            "若6时间单位内未成功逃离，爆炸触发后玩家死亡。"
            "国际部逃离属于事件出口：若该阶段国际部被摧毁，则无法通过国际部逃离。"
        ),
        opening_trigger_texts=[
            (
                "时间0 若主角位于东教学楼内部 则数学老师正在讲课，"
                "主角手机收到《皇室战争：超现实超级更新》，需在"
                "【流量更新/借马超鹏热点更新/不更新】三选一。"
            ),
            (
                "时间0 若选择流量更新 则开始按主角自身圣水规则计数，"
                "马超鹏变为离开校园状态并不可邀请。"
            ),
            (
                "时间0 若选择借马超鹏热点更新 则1时间单位内被老师发现并收手机，"
                "马超鹏停留原地等待后续事件。"
            ),
            (
                "时间3 若颜宏帆在东教学楼内部 则其下出小骷髅扰乱课堂，"
                "老师与同学逃离；若此前借了马超鹏热点，出现"
                "【告知马超鹏】选项，选择后马超鹏交出手机，主角改用其卡组并从0圣水开始。"
            ),
        ],
    )
