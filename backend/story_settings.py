"""
Module purpose:
- Provide static global story settings and trigger configuration.

Data model:
- GlobalStorySetting
  - title: story title.
  - story_text: full narrative text.
  - alert_trigger_time: school alert trigger threshold.
  - emergency_blast_delay: explosion delay after emergency starts.
  - escape_nodes_before_alert: allowed escape nodes before alert.
  - escape_nodes_during_emergency: allowed escape nodes during emergency window.

Functions:
- build_default_story_setting(): construct the default story setting requested by user.
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


def build_default_story_setting() -> GlobalStorySetting:
    """Build default global story setting."""

    return GlobalStorySetting(
        title="校园危机主线",
        story_text=(
            "时间8后校园进入警报状态。警报前玩家可从正门、后门、国际部逃离；警报后常规逃离通道关闭。"
            "若德政楼被摧毁，则进入紧急状态并启动6时间单位后的学校爆炸倒计时；"
            "紧急窗口中结界消失，可再次通过指定出口尝试逃离。"
            "若6时间单位内未成功逃离，爆炸触发后玩家死亡。"
            "国际部逃离属于事件出口：若该阶段国际部被摧毁，则无法通过国际部逃离。"
        ),
    )
