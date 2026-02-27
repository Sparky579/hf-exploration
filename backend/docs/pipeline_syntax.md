# 命令管道语法说明

`CommandPipeline` 将控制台文本命令编译为：
- 即时状态变更
- 队列动作（`move/deploy`）

## 1. 基本语法

- 一行一条命令
- 空行与 `#` 注释忽略
- 操作符：
  - `=` 赋值/执行
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
  - `time.advance=<数值>`（必须 0.5 倍数）
  - `time.advance+=<数值>`

- 全局：
  - `global.main_player=<玩家>`
  - `global.battle=<目标|none|true|false>`
  - `global.emergency=<true|false>`
  - `global.team=<同伴1,同伴2,...>`（固定格式，写入 global config）
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

## 4. 同伴规则

- 罗宾加入后主控移动耗时变为 1.5
- 许琪琪加入后主控移动耗时变为 2
- 冬雨加入后主控移动耗时变为 1.5
- 多名陪同角色同时存在时，移动耗时按最慢值计算
- 可攻略角色（romance）自然共处每 1 时间单位好感 +1（可命令行覆盖）
- 若已有可攻略角色在队伍中，再邀请另一名可攻略角色，原角色离队
- 马超鹏加入后主控切换为其手机卡组

## 5. 发现规则（引擎内置）

- 罗宾：田径场
- 许琪琪：东教学楼内部/东教学楼北路径，且时间不在 [6, 9]
- 冬雨：图书馆
- 马超鹏：时间 < 4 且位于东教学楼内部

## 6. 测试脚本

- `python backend/scripts/smoke_test.py`
- `python backend/scripts/pipeline_test.py`
- `python backend/scripts/global_trigger_check.py`
- `python backend/scripts/story_full_game_test.py`
- `python backend/scripts/companion_flow_test.py`
