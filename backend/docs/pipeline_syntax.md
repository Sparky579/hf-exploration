# 命令管道语法说明

`CommandPipeline` 用于把控制台字符串脚本编译为游戏状态变更与消息队列动作。

## 1. 基本语法

- 一行一条指令。
- 空行、`#` 开头行会忽略。
- 三种操作符：
  - `=` 赋值/指令
  - `+=` 追加文本或数值增量
  - `-=` 删除文本或数值减量

## 2. 队列动作（延迟执行）

- `<角色名>.move=<节点名>`
- `<角色名>.deploy=<卡名>`
- `<角色名>.deploy=<卡名>@<节点名>`
- `queue.flush=true`：执行当前全部队列动作
- `queue.clear=true`：清空队列

说明：
- `move`/`deploy` 进入消息队列，不会立即生效。
- 只有 `queue.flush=true` 后才真正下发到引擎。

## 3. 立即执行状态命令

- `time.advance=<数值>`：推进时间，必须是 `0.5` 的倍数
- `global.emergency=<true|false>`
- `global.battle=<目标角色名|none|true|false>`
  - `none/false` 代表不在战斗
  - 其他字符串表示“正在和谁战斗”
- `map.<节点名>.valid=<true|false>`
  - `false` 表示地点已摧毁
  - 被摧毁地点不能触发该地点内部行动（如下卡、维护身旁单位状态）

- `<角色名>.location=<节点名>`
- `<角色名>.health=<数值>`
- `<角色名>.holy_water=<数值>`
- `<角色名>.battle=<目标角色名|none>`
- `<角色名>.card_valid=<整数>`
- `<角色名>.nearby_units=<单位A:full,单位B:damaged>`
- `<角色名>.nearby_unit.<单位名>=<full|damaged|dead>`
- `<角色名>.unit.<unit_id>.health=<数值>`
  - `<=0` 视为死亡并从单位列表移除

## 4. `+=` / `-=` 数值增减

- `<角色名>.holy_water+=<数值>` / `-=`
- `<角色名>.health+=<数值>` / `-=`
- `<角色名>.card_valid+=<整数>` / `-=`
- `<角色名>.unit.<unit_id>.health+=<数值>` / `-=`
- `time.advance+=<数值>`（等价 `time.advance=<数值>`，不支持 `time.advance-=`）

## 5. 文本状态命令

- `global.state+=<文本>` / `-=`
- `<角色名>.state+=<文本>` / `-=`

## 6. 角色档案（静态描述）命令

- `character.<姓名>.status=<存活|死亡|离开校园>`
  - `离开校园` 会自动归并为 `死亡`
- `character.<姓名>.history+=<记录>`
- `character.<姓名>.history-=<记录>`
- `character.<姓名>.deck=<卡1,卡2,...,卡8>`
- `character.<姓名>.description=<文本>`

当前内置档案：
- 李再斌（敌对）
- 黎诺存（中立）
- 颜宏帆（敌对）

这些角色的“时间线行为”以 `description` 静态存储，不在引擎中自动执行；可通过上述命令在控制台手动驱动状态和历史。

## 7. 示例脚本

```txt
# 基础状态
P1.location=正门
P1.holy_water=20
P1.holy_water+=1
P1.health=10
P1.health-=2
P1.battle=李再斌
global.battle=李再斌
global.emergency=true

# 地点摧毁与校验
map.宿舍.valid=false

# 队列动作
P1.move=东教学楼南
P1.deploy=地狱飞龙
queue.flush=true
time.advance=1

# 静态角色档案维护
character.李再斌.history+=时间9摧毁宿舍
character.李再斌.status=存活
character.黎诺存.history+=时间25到达图书馆
character.颜宏帆.status=离开校园
```

## 8. 测试脚本

- 核心功能：`python backend/scripts/smoke_test.py`
- 管道与语法覆盖：`python backend/scripts/pipeline_test.py`
