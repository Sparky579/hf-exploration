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
                "时间0 若主角位于东教学楼内部 则枯燥的数学课正如催眠曲般回荡。你埋下头偷偷按亮手机，一条爆炸性的消息突然跃入眼帘——《皇室战争：超现实大更新》！"
                "你激动得掌心微汗，必须立刻决断：是忍痛烧掉自己宝贵的流量？还是厚着脸皮去借同桌马超鹏的热点？又或者……强忍好奇当做什么都没发生？"
                "选择【流量更新/借马超鹏热点更新/不更新】三选一。"
            ),
            (
                "时间0 若选择流量更新 则开始按主角自身圣水规则计数，"
                "马超鹏变为离开校园状态并不可邀请。"
            ),
            (
                "时间0 若选择借马超鹏热点更新 则虽然蹭网的快乐无与伦比，但在不到1个时间单位里，数学老师老鹰般锐利的目光就锁定了你。"
                "“交上来！”伴随一声怒喝，你的手机惨遭没收。提供热点的马超鹏逃过一劫，只能无奈地留在原地，看着你两手空空地发呆；若你此刻选择【停在原地找手机】，你能找回原本的手机和属于自己的卡组，"
                "但极度不耐烦的马超鹏会觉得你磨磨蹭蹭，丢抛下一句“不等你了”直接跑路（变为离开校园状态且不可邀请），这意味着你将永远失去获得他卡组的机会。"
            ),
            (
                "时间3 若颜宏帆在东教学楼内部 则沉闷的课堂被一声极其轻微、却又令人毛骨悚然的骨骼摩擦声打破！教室角落的阴影里，三只白森森的小骷髅悄然浮现。"
                "谁都没看清是怎么回事，而在随之爆发的惊恐和尖叫声中，始作俑者颜宏帆早已趁乱悄悄溜出了教室，没有引起任何人，包括你的注意。"
                "面对这超自然的一幕，老师和同学们惊恐地夺门而出。若你此前借了热点导致手机被收，此时可选择【告知马超鹏】。"
                "马超鹏不仅没跑，反而兴奋地塞给你他的备用机：“用我的！”接过手机的瞬间，你接管了他的强力卡组，圣水槽清零，准备迎接真正的战斗！"
            ),
            (
                "时间8 若许琪琪未被主角邀请入队 则 角色死亡:许琪琪|小骷髅击杀"
            ),
        ],
    )
