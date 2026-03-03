"""
Module purpose:
- Hold shared constants used by movement, phase control, and holy-water formulas.

Exposed symbols:
- MOVE_TIME_COST: Time consumed for one edge move.
- BASE_HOLY_WATER_PER_TIME: Base holy-water gain rate outside war.
- MAX_HOLY_WATER: Holy-water hard cap for all roles.
- PHASE_EMERGENCY: Global state key for emergency phase.
- PHASE_BATTLE: Global state key for battle phase.
"""

MOVE_TIME_COST = 1.0
BASE_HOLY_WATER_PER_TIME = 0.5  # +1 holy water per 2 time units
MAX_HOLY_WATER = 10.0

PHASE_EMERGENCY = "emergency"
PHASE_BATTLE = "battle"

# Chinese global-state mirrors used by prompt/front-end rendering.
GLOBAL_STATE_ALERT = "警报状态"
GLOBAL_STATE_EMERGENCY = "紧急状态"
GLOBAL_STATE_BARRIER_REMOVED = "结界解除"
GLOBAL_STATE_SCHOOL_EXPLOSION = "学校爆炸"

# Permanent global states (long-lived event outcomes / items / buffs).
GLOBAL_STATE_GAME_INSTALL_DONE = "永久状态:主控游戏下载完成"
GLOBAL_STATE_UNIVERSAL_KEY_OWNED = "永久道具:万能钥匙"
GLOBAL_STATE_MAGIC_SNACK_BUFF = "永久状态:魔法零食强化"

# Collapse state prefix. Final state format: `建筑坍塌:<target>`.
GLOBAL_STATE_COLLAPSE_PREFIX = "建筑坍塌:"

# Dynamic event markers shared across modules.
DYNAMIC_LZB_DEZHENG_PENDING = "待决事件:李再斌德政楼装置引爆"
DYNAMIC_LZB_DEZHENG_BANNED = "事件封禁:李再斌死亡导致德政楼敌对引爆取消"
DYNAMIC_GYM_INTERLUDE_DONE = "场景事件:体育馆校歌间奏沉睡已触发"
