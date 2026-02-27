# 命令管道语法说明

`CommandPipeline` 将控制台文本命令编译为：
- 立即生效的状态变更
- 或进入消息队列的动作（`move` / `deploy`）

## 1. 基本语法

- 一行一条指令
- 空行和 `#` 注释行会忽略
- 三种操作符：
  - `=` 赋值/动作
  - `+=` 文本追加或数值增量
  - `-=` 文本删除或数值减量

## 2. 队列动作

- `<角色名>.move=<节点名>`
- `<角色名>.deploy=<卡名>`
- `<角色名>.deploy=<卡名>@<节点名>`
- `queue.flush=true` 执行队列
- `queue.clear=true` 清空队列

## 3. 立即命令

- 时间：
  - `time.advance=<数值>`（必须是 0.5 的倍数）
  - `time.advance+=<数值>`（等价于上面）

- 全局：
  - `global.emergency=<true|false>`
  - `global.battle=<目标角色名|none|true|false>`（战斗状态是字符串）
  - `global.main_player=<玩家名>`
  - `global.state+=<文本>`
  - `global.state-=<文本>`

- 地图：
  - `map.<节点名>.valid=<true|false>`
  - `false` 表示节点被摧毁
  - 节点被摧毁后，无法触发该节点内部行动（如部署、维护身旁单位状态）

- 角色：
  - `<角色名>.location=<节点名>`
  - `<角色名>.escape=<节点名>`
  - `<角色名>.health=<数值>`
  - `<角色名>.holy_water=<数值>`
  - `<角色名>.battle=<目标角色名|none>`
  - `<角色名>.card_valid=<整数>`
  - `<角色名>.state+=<文本>`
  - `<角色名>.state-=<文本>`
  - `<角色名>.nearby_units=<单位A:full,单位B:damaged>`
  - `<角色名>.nearby_unit.<单位名>=<full|damaged|dead>`
  - `<角色名>.unit.<unit_id>.health=<数值>`（`<=0` 自动移除）

- 角色档案（静态）：
  - `character.<姓名>.status=<存活|死亡|离开校园>`
  - `character.<姓名>.history+=<文本>`
  - `character.<姓名>.history-=<文本>`
  - `character.<姓名>.deck=<卡1,卡2,...,卡8>`
  - `character.<姓名>.description=<文本>`

## 4. 数值 `+=` / `-=`

支持：
- `<角色>.holy_water`
- `<角色>.health`
- `<角色>.card_valid`（增减值必须为整数）
- `<角色>.unit.<unit_id>.health`
- `time.advance`（仅支持 `+=`，不支持 `-=`）

## 5. 全局故事与触发规则

默认故事配置：
- 时间 `> 8` 触发校园警报状态
- 警报前可从：`正门` / `后门` / `国际部` 逃离
- 警报后常规逃离关闭
- 若 `德政楼` 被摧毁，触发紧急状态（双倍圣水）
- 紧急状态开始后 6 时间单位，学校爆炸
- 紧急窗口内结界消失，可再次通过指定出口逃离
- 若此时 `国际部` 被摧毁，则无法通过 `国际部` 逃离
- 若主控玩家 `HP <= 0`，游戏立即结束

## 6. 示例

```txt
global.main_player=P1
P1.location=正门
P1.holy_water=20
P1.holy_water+=1
P1.health=10
P1.health-=2

global.battle=李再斌
P1.battle=李再斌
global.state+=全局动态：演练开始

P1.move=东教学楼南
P1.deploy=地狱飞龙
queue.flush=true
time.advance=1

map.德政楼.valid=false
time.advance=0.5
P1.escape=后门
```

## 7. 测试脚本

- `python backend/scripts/smoke_test.py`
- `python backend/scripts/pipeline_test.py`
- `python backend/scripts/global_trigger_check.py`
- `python backend/scripts/story_full_game_test.py`
