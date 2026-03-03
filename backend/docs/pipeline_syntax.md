# 命令管道语法说明

`CommandPipeline` 会把控制台命令编译为：
1. 即时状态变更
2. 队列动作（`move` / `deploy`）

## 1. 基本语法
- 一行一条命令
- 空行和 `#` 注释会忽略
- 模型输出推荐统一方括号格式：`[global.main_player=主控玩家]`（系统会自动去壳解析）
- 操作符：
  - `=` 赋值
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
  - `time.advance=<数值>`（必须是 0.5 的倍数）
  - `time.advance+=<数值>`

- 全局：
  - `global.main_player=<玩家>`
  - `global.battle=<目标角色名|none>`
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
  - `<角色>.nearby_units=<单位A:full,单位B:damaged>`（全量覆盖，不推荐）
  - `<角色>.nearby_units+=<单位A:full,单位B:damaged>`（增量合并，推荐）
  - `<角色>.nearby_units-=<单位A,单位B>`（按名称移除，推荐）
  - `<角色>.nearby_unit.<单位>=<full|damaged|dead>`（支持中文同义：存活/受伤/死亡）
  - `<角色>.nearby_unit.<单位>.health=<数值>`
  - `<角色>.nearby_unit.<单位>.health+=<数值>`
  - `<角色>.nearby_unit.<单位>.health-=<数值>`
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

- Trigger / 事件：
  - `trigger.add=<句子>`
  - `trigger.remove=<id 或原句>`
  - `trigger.clear=true`
  - `scene_event.trigger=<event_id>`
  - `game_event.trigger=<event_id>`
  - `event.rocket_launch=<建筑或地点>`

说明：
- `game_event.trigger` 用于触发后端既定事件（例如游戏下载/安装）。
- 既定事件若包含固定耗时（如 2 时间单位），由后端自动推进时间；模型不应再手动写 `time.advance`。

## 4. Trigger 句子格式
推荐格式：
- `时间8 若德政楼被摧毁 则 进入紧急状态`
- `角色:颜宏帆|时间3 若颜宏帆在东教学楼内部 则 颜宏帆下出小骷髅`

规则：
- 当 `current_time >= trigger_time` 时，trigger 会被标记为触发。
- 敌对角色 trigger 会由隐藏线程处理并继续生成下一条 trigger。

## 5. 特殊事件
- `event.rocket_launch=<建筑名>` 会立即写入“火箭升空提示”，并自动创建 1 时间单位后的坍塌 trigger。
- 坍塌 trigger 的推荐结果写法：`建筑倒塌:<建筑名>`。

## 6. 日志
`CommandPipeline` 会维护最近命令日志：
- `time`：执行时全局时间
- `command`：原始命令
- `status`：`ok` 或 `error`
- `detail`：执行说明或错误信息
