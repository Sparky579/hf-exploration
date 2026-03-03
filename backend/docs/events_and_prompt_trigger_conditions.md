# 事件与 Prompt 触发条件说明

本文档说明两件事：

1. 后端有哪些“事件”（`scene_event` / `game_event`）。
2. 这些事件在什么条件下会被放进发给大模型的 prompt。

文件对应实现：

- 事件构建：`backend/state_snapshot.py`
- Prompt 组装与合并：`backend/llm_prompting.py`

---

## 1. Prompt 注入总规则

### 1.1 当前地点事件

每轮都会基于主控当前地点构建：

- `scene_events = _build_scene_events(...)`
- `predefined_events = _build_predefined_events(...)`

### 1.2 目标地点事件（静态解析）

每轮还会做一次“本轮可能前往地点”预测：

- `predicted_next_node = _predict_next_node_from_input(...)`

若解析到目标地点（且与当前不同），会再额外构建该地点的：

- `predicted_scene_events`
- `predicted_predefined_events`
- `predicted_nearby_trigger_hints`
- `predicted_nearby_trigger_hints_n_to_n_plus_2_0`

### 1.3 合并策略（最终给模型）

`backend/llm_prompting.py` 会把“当前地点 + 目标地点”的事件合并去重后给模型：

- `scene_events`（合并后）
- `predefined_events`（合并后）
- `nearby_trigger_hints`（合并后）
- `nearby_trigger_hints_n_to_n_plus_2_0`（合并后）

也就是说：**不是全图事件都给，只给当前与目标地点相关事件**。

---

## 2. 静态地点解析规则

`_predict_next_node_from_input` 规则如下：

1. 输入含邻接节点名（例如“去东教学楼北”）。
2. 输入含邻接节点名（全图匹配后再限制为邻接）。
3. 输入为纯数字（例如 `1`）：
   - 从最近一条 `System:` 文本中解析选项行（`1. ...` / `1、...`）。
   - 在该选项文本里提取邻接节点名。

若解析失败，则 `predicted_next_node=None`，本轮只注入当前地点事件。

---

## 3. Scene Events（模型可决定是否触发）

以下事件来自 `_build_scene_events`：

1. `opening_phone_choice_window`
   - 条件：`t<5`、非战斗、主控在`东教学楼内部`、且开局手机分支未完结（未持有马超鹏主手机、未走流量分支、未完成交机）。
   - 事件提示（`narrative_hint`）会明确交给模型：
     - 借马超鹏热点会触发“数学老师收手机”链路。
     - 若不借热点（如流量更新/错过借机窗口），会失去后续邀请马超鹏入队并接管其手机卡组的机会。

2. `east_toilet_yanhongfan_encounter`
   - 条件：未触发过、非战斗、`t<=5`、主控在`东教学楼内部`、颜宏帆存活。

3. `international_it_teacher_encounter`
   - 条件：国际部信息老师事件未完结且未 pending、非战斗、主控在`国际部`、国际部有效、警报前正常时间、`t<=alert_trigger_time`、信息老师存活。

4. `south_building_chenluo_heal_encounter`
   - 条件：未触发、非战斗、主控在`南教学楼`、节点有效、`t<10`、陈洛存活。

5. `dezheng_blue_device_observation`
   - 条件：未发现且未摧毁、非战斗、主控在`德政楼`、节点有效。

6. `gate_guard_blockade_observation`
   - 条件：在门口节点（正门/后门）且保安事件未见/未破、非战斗。

7. `canteen_liqinbin_prompt`
   - 条件：李秦彬事件未 pending 且未完成、非战斗、主控在`食堂`、节点有效、李秦彬存活。

8. `canteen_universal_key_prompt`
   - 条件：未持有钥匙且未 pending、非战斗、主控在`食堂`、节点有效。

9. `store_iron_gate_observation`
   - 条件：小卖部门未开未破且未见过、非战斗、主控在`小卖部`、节点有效。

10. `gym_iron_gate_observation`
   - 条件：体育馆门未开且未见过、非战斗、主控在`体育馆`、节点有效。

---

## 3.1 开局事件 Prompt 示例（关键）

当触发条件满足时，传给模型的 `scene_events` 中会包含类似条目（简化示意）：

```json
{
  "id": "opening_phone_choice_window",
  "title": "开局课堂：手机更新方式抉择",
  "trigger_when": "t<5 且主控在东教学楼内部，且开局手机分支尚未完结",
  "trigger_command": "[scene_event.trigger=opening_phone_choice_window]",
  "narrative_hint": "这是开局关键分支：若选择借马超鹏热点，数学老师会收走主控手机；后续课堂骚乱节点马超鹏可能把他的主手机交给你。若不借热点（如走流量更新/错过借机窗口），会失去后续邀请马超鹏入队并接管其手机卡组的机会。"
}
```

---

## 4. Predefined Events（模型触发后由后端结算）

以下事件来自 `_build_predefined_events`：

1. `destroy_dezheng_blue_device_with_heavy`
   - 条件：蓝光装置已发现且未摧毁、主控在`德政楼`、节点有效。

2. `break_gate_guard_blockade_with_units`
   - 条件：门口保安已见且未突破（并计算当前战力）。

3. `international_it_teacher_reveal_confiscate`
   - 条件：**`INTL_TEACHER_EVENT_PENDING` 已存在**，且主控在`国际部`、国际部有效、信息老师存活。
   - 注：这是“走近看清人影”后的后端结算事件（包含收手机/卸载或常规劝导分支）。

4. `canteen_liqinbin_remind_and_token`
   - 条件：李秦彬 pending 激活，且主控在`食堂`、节点有效、李秦彬存活。

5. `canteen_collect_universal_key`
   - 条件：尚未拿到钥匙、主控在`食堂`、节点有效。

6. `unlock_store_iron_gate_with_key`
   - 条件：已持钥匙、主控在`小卖部`、节点有效、铁门未开未破。

7. `break_store_iron_gate_with_heavy`
   - 条件：与上条同场景，同时提供重型火力校验信息。

8. `unlock_gym_iron_gate_with_key`
   - 条件：已持钥匙、主控在`体育馆`、节点有效、铁门未开。

9. `install_update_game_with_ma_phone`
   - 条件：主控游戏未安装、且持有马超鹏主手机标记。

10. `install_update_game_with_own_phone`
    - 条件：主控游戏未安装、且未持有马超鹏主手机。

---

## 5. 开局“数学老师收手机 / 马超鹏交手机”为什么现在既有事件也有触发提示

现在有两层来源：

1. `scene_event`：

- `opening_phone_choice_window`（`t<5` 开局抉择事件）

2. 全局 scripted triggers：

- “选择借马超鹏热点更新 -> 手机被数学老师收走”
- 后续马超鹏交手机分支

这些信息通过：

- `nearby_trigger_hints`
- `nearby_trigger_hints_n_to_n_plus_2_0`

进入 prompt。

为避免被地点过滤误丢失，已调整为：

- **`owner=global` 的触发器在当前窗口内始终视为相关**（会进入提示）。

---

## 6. 常见排查

1. 看不到 `international_it_teacher_reveal_confiscate`
   - 先确认是否已触发 `scene_event.trigger=international_it_teacher_encounter` 让系统写入 pending。
   - 再确认主控当前（或静态解析目标）是`国际部`。

2. 看不到开局“借热点被收手机”链
   - 确认时间窗口在开局触发器附近（通常 `t=1~3`）。
   - 确认使用的是新会话（旧会话可能仍是旧逻辑）。

3. 输入数字选项后没识别目标地点
   - 需要最近一条 `System:` 文本里存在标准编号选项行（如 `1. 去XXX`）。
