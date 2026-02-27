# 命令管道语法说明

`CommandPipeline` 会把控制台文本命令编译为：
1. 即时状态变更
2. 队列动作（`move/deploy`）

## 1. 基本语法
- 一行一条命令
- 空行和 `#` 注释会忽略
- 支持操作符：
  - `=` 赋值执行
  - `+=` 文本追加或数值增加
  - `-=` 文本删除或数值减少

## 2. 队列动作
- `<角色>.move=<节点>`
- `<角色>.deploy=<卡名>`
- `<角色>.deploy=<卡名>@<节点>`
- `queue.flush=true`
- `queue.clear=true`

## 3. 即时命令
- 时间：
  - `time.advance=<数值>`（必须是 0.5 倍数）
  - `time.advance+=<数值>`

- 全局：
  - `global.main_player=<玩家>`
  - `global.battle=<目标|none|true|false>`
  - `global.emergency=<true|false>`
  - `global.team=<同伴1,同伴2,...>`
  - `global.team+=<同伴>`
  - `global.team-=<同伴>`
  - `global.state+=<文本>`
  - `global.state-=<文本>`

- 地图：
  - `map.<节点>.valid=<true|false>`

- 角色：
  - `<角色>.location=<节点>`
  - `<角色>.escape=<节点>`
  - `<角色>.discover=<同伴名>`
  - `<角色>.invite=<同伴名>`
  - `<角色>.health=<数值>`
  - `<角色>.health+=<数值>`
  - `<角色>.health-=<数值>`
  - `<角色>.holy_water=<数值>`
  - `<角色>.holy_water+=<数值>`
  - `<角色>.holy_water-=<数值>`
  - `<角色>.battle=<目标|none>`
  - `<角色>.card_valid=<整数>`
  - `<角色>.card_valid+=<整数>`
  - `<角色>.card_valid-=<整数>`
  - `<角色>.state+=<文本>`
  - `<角色>.state-=<文本>`
  - `<角色>.nearby_units=<单位A:full,单位B:damaged>`
  - `<角色>.nearby_unit.<单位>=<full|damaged|dead>`
  - `<角色>.unit.<unit_id>.health=<数值>`
  - `<角色>.unit.<unit_id>.health+=<数值>`
  - `<角色>.unit.<unit_id>.health-=<数值>`

- 角色档案：
  - `character.<姓名>.status=<存活|死亡|离开校园>`
  - `character.<姓名>.history+=<文本>`
  - `character.<姓名>.history-=<文本>`
  - `character.<姓名>.deck=<卡1,...,卡8>`
  - `character.<姓名>.description=<文本>`

- 同伴状态：
  - `companion.<姓名>.discovered=<true|false>`
  - `companion.<姓名>.in_team=<true|false>`
  - `companion.<姓名>.affection=<数值>`
  - `companion.<姓名>.affection+=<数值>`
  - `companion.<姓名>.affection-=<数值>`
  - `companion.<姓名>.noticed_by=<敌对1,敌对2,...>`
  - `companion.<姓名>.noticed_by+=<敌对>`
  - `companion.<姓名>.noticed_by-=<敌对>`

- 动态 Trigger：
  - `trigger.add=<句子>`
  - `trigger.remove=<id 或原句>`
  - `trigger.clear=true`

## 4. Trigger 句子格式
推荐格式：`时间8 若德政楼被摧毁 则进入紧急状态`  
时间推进后若 `current_time > trigger_time`，系统会标记触发并写入触发历史日志。

## 5. 日志
`CommandPipeline` 会维护最近命令日志，字段包括：
- `time`：执行时全局时间
- `command`：原始命令
- `status`：`ok` 或 `error`
- `detail`：执行说明或错误信息
