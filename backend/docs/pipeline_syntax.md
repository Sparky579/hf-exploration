# 命令管道语法说明

本系统提供 `CommandPipeline`，用于把字符串脚本“编译”为游戏操作。

## 1. 基本规则

- 一行一条指令。
- 空行和 `#` 开头的行会被忽略。
- 支持三种操作符：
  - `=` 赋值/指令
  - `+=` 追加文本状态
  - `-=` 删除文本状态

## 2. 队列与即时执行

- **进入消息队列**（延迟执行）：
  - `<角色名>.move=<节点名>`
  - `<角色名>.deploy=<卡名>`
  - `<角色名>.deploy=<卡名>@<节点名>`
- **即时执行**（编译时立即生效）：
  - `time.advance=<数值>`
  - `global.battle=<true|false>`
  - `global.emergency=<true|false>`
  - `<角色名>.location=<节点名>`
  - `<角色名>.health=<数值>`
  - `<角色名>.holy_water=<数值>`
  - `<角色名>.card_valid=<整数>`
  - `<角色名>.nearby_units=<单位A:full,单位B:damaged>`
  - `<角色名>.nearby_unit.<单位名>=<full|damaged|dead>`
  - `<角色名>.unit.<unit_id>.health=<数值>`
  - `global.state+=<文本>` / `global.state-=<文本>`
  - `<角色名>.state+=<文本>` / `<角色名>.state-=<文本>`
- 队列控制：
  - `queue.flush=true` 执行所有排队消息
  - `queue.clear=true` 清空队列

## 3. 时间规则

- `time.advance` 必须是 `0.5` 的倍数。
- 角色移动一条边耗时由 `MOVE_TIME_COST` 控制（当前为 `1.0`）。
- 只有调用 `time.advance`，排队的移动才会真正完成。

## 4. 出牌与卡组规则

- 每个玩家 `card_deck` 固定 8 张。
- 前 `card_valid` 张可出牌（默认 4）。
- 出牌会消耗卡牌 `consume` 圣水。
- 每次出牌后，卡组执行轮转：
  - 第 1 张移到第 8 位，后面依次前移。

## 5. 身旁单位列表

- 角色维护 `nearby_units`（单位名 -> 状态）。
- 状态只有：
  - `full`（满血）
  - `damaged`（残血）
  - `dead`（删除该单位，不再出现在列表中）

## 6. 示例脚本

```txt
# 即时状态
P1.location=正门
P1.health=8
P1.holy_water=20
global.state+=全局动态：演练开始
P1.state+=角色动态：进入战备
P1.nearby_units=地狱飞龙:full,巨人:damaged
P1.nearby_unit.巨人=dead

# 入队
P1.move=东教学楼南
P1.deploy=地狱飞龙
queue.flush=true

# 时间推进与阶段控制
time.advance=1
global.battle=true
time.advance=0.5
```

## 7. 测试脚本

- 核心测试：`python backend/scripts/smoke_test.py`
- 管道语法测试：`python backend/scripts/pipeline_test.py`
