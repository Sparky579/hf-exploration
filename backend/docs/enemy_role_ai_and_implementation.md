# 敌对角色AI与实现

## 目标
后端已不再使用“敌对角色 LLM 线程”。  
敌对角色由纯逻辑调度器驱动，按时间推进执行。

实现文件：`backend/enemy_director.py`

## 总体机制
1. `GameEngine.advance_time(amount)` 调用 `enemy_director.on_time_advanced(amount)`。
2. 每个敌对角色有一套 `EnemyPlan`（步骤列表）。
3. 每个步骤有：
- `delay`：执行前倒计时
- `action`：动作类型（如 `move_towards` / `deploy_priority`）
- `payload`：动作参数
4. 倒计时支持暂停，恢复后继续，不重置。

## 暂停规则
触发任一条件即暂停当前角色倒计时：
1. 角色死亡
2. 角色正在移动
3. `global.battle` 指向该角色（处于战斗）
4. 该角色有 `battle_target`
5. 与主控在同一节点

对应状态会写入 `paused_reason`（用于调试）。

## 默认敌对角色计划
### 李再斌（`li_mainline_v1`）
按步骤循环：
1. `delay=6.0` 向国际部移动
2. `delay=1.0` 优先出牌：皮卡超人/野蛮人攻城锤/火球
3. `delay=1.0` 向东教学楼南移动
4. `delay=1.0` 向西教学楼南移动
5. `delay=1.0` 再次优先出牌：野蛮人攻城锤/火球/皮卡超人
6. `delay=2.0` 向德政楼移动
7. `delay=2.0` 回宿舍

### 颜宏帆（`yan_mainline_v1`）
按步骤循环：
1. `delay=2.0` 优先出牌：骷髅兵/野猪骑士
2. `delay=1.0` 向东教学楼南移动
3. `delay=2.0` 再次优先出牌：野猪骑士/火球/火枪手
4. `delay=2.0` 向西教学楼南移动
5. `delay=2.0` 回东教学楼内部

### 其他敌对角色
使用 `enemy_fallback_idle_v1`：周期写入一条“lurking”状态（保底不崩）。

## 动作语义
### `move_towards`
1. 通过 BFS 求下一跳
2. 调 `engine.issue_move(role, hop)`
3. 无路径则 `skip`
4. 移动冲突则 `retry`（默认 1.0 时间后重试）

### `deploy_priority`
1. 仅对已是 `PlayerRole` 的敌对角色生效
2. 只在当前可用窗口内选牌（`card_valid`）
3. 校验圣水足够才可下牌
4. 失败返回 `retry`（圣水不足、窗口不可用等）

## 调试可见性
`state_snapshot` 已加入：
- `global_state.enemy_director`

字段包含：
- `plan_id`
- `step_index`
- `next_step_id`
- `remaining_time`
- `paused_reason`
- `completed`

