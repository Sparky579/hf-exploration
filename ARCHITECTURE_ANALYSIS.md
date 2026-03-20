# HF-Exploration 架构分析：四维约束框架

> 本文档基于四维分析框架（触发机制、上下文组装、效果执行、权限作用域），详细解剖本项目中每一个决策节点所对应的约束类型、适用条件及代码位置。

---

## 项目总览

本项目是一个基于大模型的校园叙事 RPG 引擎。玩家通过自然语言输入行动（限 15 字），后端将行动与完整游戏状态组装为 Prompt 发送给 LLM（Gemini / OpenAI），LLM 返回剧情文本 + `[command]...[/command]` 结构化指令块，后端解析指令并修改游戏状态。

**核心代码文件：**

| 文件 | 行数 | 职责 |
|------|------|------|
| `app.py` | 876 | FastAPI 服务端，会话管理，流式响应 |
| `engine.py` | 711 | 游戏引擎核心，时间驱动、状态突变、同伴系统 |
| `command_pipeline.py` | 1516 | 命令解析与执行，队列管理，场景/游戏事件处理 |
| `llm_agent_bridge.py` | 289 | LLM 流式输出桥接，命令提取与过滤 |
| `llm_prompting.py` | 1347 | Prompt 构建，上下文压缩与过滤 |
| `state_snapshot.py` | 1496 | 游戏状态序列化快照，感知范围计算 |
| `global_config.py` | 499 | 全局时间线、状态标签、同伴注册表、脚本触发器 |
| `global_event_checker.py` | 408 | 硬编码故事触发（警报/紧急/爆炸）、逃跑验证 |
| `enemy_director.py` | 824 | 确定性敌方 AI 行为计划（无 LLM） |

---

## 维度一：触发机制（Triggering Mechanism）

> "什么时候唤醒大模型？什么时候不需要大模型？"

### Level 0：纯硬编码触发（Deterministic Trigger）

本项目大量使用纯硬编码触发，0 Token 消耗。

#### 1.1 时间阈值触发

**警报状态触发（t > 8.0）**

```python
# global_event_checker.py:87-92
if (not self.state.alert_triggered) and now > self.story_setting.alert_trigger_time:
    self.state.alert_triggered = True
    self.engine.global_config.add_global_state(GLOBAL_STATE_ALERT)
```

- **条件**：纯数值比较 `current_time > 8.0`
- **约束类型**：时间阈值硬门槛
- **适用场景**：全局不可逆叙事节点（警报一旦触发不可撤销）
- **为什么用 Level 0**：这是全局主线的关键分支点，必须绝对可靠、零延迟触发，不能依赖 LLM 判断"是否该响警报了"

**学校爆炸触发（t >= emergency_start + 6.0）**

```python
# global_event_checker.py:97-111
if (self.state.emergency_triggered
    and (not self.state.explosion_triggered)
    and self.state.explosion_time is not None
    and now >= self.state.explosion_time):
    self.state.explosion_triggered = True
    # 杀死所有未逃离角色
    for role_name in list(self.engine.campus_map.roles.keys()):
        if role_name in self.state.escaped_roles:
            continue
        self.engine.set_role_health(role_name, 0)
```

- **条件**：复合数值判断 `紧急状态已触发 AND 当前时间 >= 爆炸时间`
- **约束类型**：倒计时硬截止 + 批量状态突变
- **适用场景**：游戏终局（Game Over）判定
- **为什么用 Level 0**：这是"全灭"级别的终极后果，一帧延迟或判断偏差都不可接受

**NPC 限时离场（陈洛 t >= 11.0）**

```python
# global_event_checker.py:115-136
if now < 11.0:
    return
if "陈洛" not in self.engine.character_profiles:
    return
profile = self.engine.get_character_profile("陈洛")
if profile.status != "存活":
    return
if self.SOUTH_BUILDING_CHENLUO_DONE in set(self.engine.global_config.dynamic_states):
    return
profile.set_status("离开校园")
```

- **条件**：`time >= 11 AND 陈洛存活 AND 未触发南教学楼治疗事件`
- **约束类型**：时间窗口 + 条件门控
- **适用场景**：限时 NPC 可用性窗口
- **为什么用 Level 0**：NPC 的存在/缺席影响后续场景事件可用性，不能让 LLM 来决定"陈洛什么时候走"

**许琪琪死亡触发（t >= 8.0 且未入队）**

```python
# story_settings.py:70-71（作为 opening_trigger_texts 加载）
"时间8 若许琪琪未被主角邀请入队 则 角色死亡:许琪琪|小骷髅击杀"
```

- **条件**：时间阈值 + 同伴状态检查
- **约束类型**：脚本化触发器 with 条件检查
- **执行路径**：`global_event_checker._check_scripted_triggers()` → `_is_scripted_condition_met()` → `_apply_character_death()`
- **适用场景**：玩家未在时间窗口内完成某行动的惩罚
- **为什么用 Level 0**：这是"不行动的后果"，纯游戏逻辑判断，LLM 不应该有权决定"许琪琪是否该死"

#### 1.2 状态条件触发

**紧急状态触发（德政楼被摧毁时）**

```python
# global_event_checker.py:94-95
if (not self.state.emergency_triggered) and (not self.engine.campus_map.is_node_valid("德政楼")):
    self._trigger_emergency(now)
```

- **条件**：地图节点有效性检查 `is_node_valid("德政楼") == False`
- **约束类型**：状态变化感知触发
- **适用场景**：因果链的关键环节——建筑倒塌引发全局相变
- **为什么用 Level 0**：这是物理后果（建筑倒了 → 紧急状态），不需要语义判断

**马超鹏手机交接（t >= 3 且主控无可用手机）**

```python
# global_event_checker.py:385-407
if now < 3 or self.OPENING_HANDOFF_DONE in states:
    return
if self.engine.global_config.main_game_state not in ("confiscated", "not_installed", "downloading"):
    return
# 强制交接
self.engine.set_companion_discovered("马超鹏", True)
self.engine.set_companion_in_team("马超鹏", True)
self.engine.set_player_card_deck(main_name, list(ma_profile.deck))
self.engine.set_main_game_state("installed")
```

- **条件**：`t >= 3 AND 手机状态为 confiscated/not_installed/downloading AND 尚未交接`
- **约束类型**：兜底保护机制（确保玩家最终能获得游戏能力）
- **为什么用 Level 0**：这是防止游戏卡死（softlock）的硬性保障

#### 1.3 敌方 AI 确定性行为计划（EnemyDirector）

整个敌方行为系统是 **纯确定性** 的，0 Token 消耗。

```python
# enemy_director.py:91-92
class EnemyDirector:
    """Advance fixed hostile-role plans with pause-aware counters."""
```

三个敌对角色的所有行动都预编写为固定步骤序列：

| 角色 | 行动示例 | 触发时间 |
|------|---------|---------|
| 颜宏帆 | 在东教学楼释放骷髅 | t=3 |
| 颜宏帆 | 摧毁西教学楼 | t=11 |
| 黎诺存 | 部署哥布林团伙 | t=8 |
| 黎诺存 | 向东教学楼发射火箭 | t=19 |
| 李再斌 | 在宿舍部署皮卡超人 | t=7 |
| 李再斌 | 攻城锤摧毁国际部 | t=16 |
| 李再斌 | 引爆德政楼 | t=24 |

**暂停感知机制**：

```python
# enemy_director.py:99-100
def on_time_advanced(self, amount: float) -> None:
    if amount <= 0:
        return
    # 检查每个角色是否处于暂停状态（移动中、战斗中、死亡）
    # 只有非暂停角色才消耗计时器
```

- **约束类型**：固定时间表 + 暂停条件
- **适用场景**：敌对势力的行为必须可预测、可规划
- **为什么用 Level 0**：敌方行为是整个故事骨架的一部分。如果让 LLM 控制敌方，可能出现"李再斌突然变好人"这种叙事崩坏

#### 1.4 移动预测与自动执行

```python
# app.py:298-329
def _try_auto_apply_main_move(engine, pipeline, action_text, recent_user_turns):
    target = _predict_next_node_from_input(
        engine=engine, current_node=current_node,
        current_user_input=action_text, recent_user_turns=recent_user_turns,
    )
    if not target or target == current_node:
        return None
    node = engine.campus_map.get_node(current_node)
    if target not in set(node.neighbors):
        return None
    # 自动执行移动 + 时间推进
    pipeline.compile_line(f"[{main_name}.move={target}]")
    pipeline.compile_line("[queue.flush=true]")
    pipeline.compile_line(f"[time.advance={move_cost:g}]")
```

- **条件**：关键词匹配（"向西走" → 西教学楼南）+ 邻接性验证
- **约束类型**：硬编码关键词匹配 + 图论邻接校验
- **触发层级**：Level 0（关键词匹配）→ 后端直接执行（不等 LLM）
- **为什么不让 LLM 做**：移动是高频操作，延迟必须最小化。且移动合法性（邻接）必须绝对可靠

---

### Level 1：硬编码兜底 + 语义微调（Hybrid Gating）

本项目的主叙事循环属于此级别。

#### 1.5 每回合 LLM 调用（玩家输入 → LLM 生成）

```python
# app.py:496-817
async def take_action(req: ActionRequest):
    # 硬编码前置：
    # 1. 会话存在性检查
    # 2. 游戏结束检查
    # 3. 输入长度校验 (≤15字)
    # 4. 自动移动尝试
    # 5. 失败命令重试

    # 然后才调用 LLM：
    for event in bridge.run_step_stream(...):
        ...
```

**触发条件的层次结构：**

1. **硬编码前门（必须通过）**：会话有效、游戏未结束、输入合法
2. **硬编码优化（可选旁路）**：自动移动如果成功，LLM 就不再处理移动
3. **LLM 语义处理**：通过前门后，LLM 生成叙事 + 命令

这是典型的 **"先硬后软"混合门控**：硬逻辑过滤掉无效请求，通过后才消耗 Token。

#### 1.6 场景事件的触发条件

场景事件（scene_event）在 `state_snapshot.py` 中构建时，会预先评估触发条件：

```python
# state_snapshot.py 中 _build_scene_events() 的逻辑
# 只在以下条件满足时，才将事件列入 LLM 可见上下文：
# - 玩家位于正确位置
# - 时间窗口内
# - 前置条件满足（如未触发过同一事件）
# - 非战斗状态
```

然后 LLM 在 Prompt 中看到可用事件列表，由 LLM 判断"是否在叙事中触发此事件"——这就是 **Level 1 的精髓：硬编码决定"能不能触发"，LLM 决定"要不要在这个叙事节点触发"**。

---

### Level 2：全语义触发

本项目中 **不存在** 纯 Level 2 触发。所有 LLM 调用都有硬编码前置条件。这是一个有意识的设计选择——在校园危机的有限时间窗口内（t=0~30），不允许 LLM "自己决定什么时候行动"。

---

## 维度二：上下文组装策略（Context Assembly Strategy）

> "大模型能看到什么？"

本项目的上下文组装非常精密，是整个架构最复杂的部分（`state_snapshot.py` 1496 行 + `llm_prompting.py` 1347 行）。

### Level 1：规则变量注入（Variable Injection）

#### 2.1 全局状态注入

```python
# state_snapshot.py:153-182
payload = {
    "global_state": {
        "time": engine.global_config.current_time_unit,
        "states": list(engine.global_config.global_states),       # 警报/紧急/爆炸
        "dynamic_states": list(engine.global_config.dynamic_states),
        "battle_state": engine.global_config.battle_state,
        "main_game_state": engine.global_config.main_game_state,
        "can_main_player_gain_holy_water": engine.global_config.can_main_player_gain_holy_water,
        "main_player": engine.main_player_name,
        "team_companions": engine.global_config.list_team_companions(),
        "scripted_triggers": engine.global_config.list_scripted_triggers(),
        "enemy_director": engine.enemy_director.snapshot(),
        # ...
    },
}
```

**注入的精确变量包括：**

| 变量 | 类型 | 示例值 | 含义 |
|------|------|--------|------|
| `time` | float | `5.0` | 当前时间刻度 |
| `states` | string[] | `["警报状态"]` | 全局永久状态标签 |
| `battle_state` | string\|null | `"颜宏帆"` | 当前交战对象 |
| `main_game_state` | string | `"installed"` | 手机/游戏安装状态 |
| `holy_water` | float | `3.5` | 当前圣水量 |
| `card_deck` | string[8] | `["地狱飞龙",...]` | 卡组 |
| `card_valid` | int | `4` | 可用卡牌窗口大小 |

**约束类型**：开发者精确控制 LLM 的信息输入，只暴露需要知道的数值状态。LLM 不会看到引擎内部实现细节。

#### 2.2 主控玩家状态注入

```python
# state_snapshot.py:235-279
def extract_main_player_state(engine):
    return {
        "name": player.name,
        "health": role.health,
        "holy_water": player.holy_water,
        "location": role.current_location,
        "moving": role.query_movement_status(),
        "battle_target": role.battle_target,
        "dynamic_states": role.list_dynamic_states(),
        "nearby_units": role.list_nearby_units(),
        "card_deck": list(player.card_deck),
        "card_valid": player.card_valid,
        "playable_cards": player.playable_cards(),
        "playable_cards_detail": playable_cards_detail,
        "active_units": active_units,  # 含攻击力/血量/飞行/位置
    }
```

**注意 `playable_cards_detail`**：系统预计算了每张卡牌是否可用（圣水够不够、排序到没到），直接告诉 LLM "这些卡现在能打，这些不能"——而不是让 LLM 自己算。

#### 2.3 场景与角色注入

```python
# state_snapshot.py:306-342
def extract_scene_state(engine, node_name):
    return {
        "name": node.name,
        "valid": node.valid,
        "neighbors": sorted(node.neighbors),
        "scene_paragraph": get_scene_paragraph(node.name),  # 场景描写文本
        "roles": scene_roles,  # 当前位置所有角色
        "unit_presence": _extract_scene_unit_presence(engine, node_name),
    }
```

### Level 1+ ：基于规则的动态过滤（Algorithmic Filtering）

本项目在 Level 1 基础上增加了大量 **基于规则的过滤逻辑**，介于 Level 1 和 Level 2 之间。

#### 2.4 感知范围过滤

```python
# state_snapshot.py:345-350
def _build_sensing_scope(engine, center_node):
    neighbors = sorted(engine.campus_map.get_node(center_node).neighbors)
    return {
        "center_node": center_node,
        "nearby_nodes": [center_node, *neighbors],
    }
```

**规则**：LLM 只能看到主控所在节点 + 相邻节点的角色和单位。远距离角色只得到一行简述：

```python
# llm_prompting.py 中的处理：
# must_full_desc_roles = 队友 + 当前节点角色 + 目标节点角色 + 事件相关角色
# 其他角色 → 一行摘要（名字+位置），不含完整描述/历史/卡组
```

- **约束类型**：空间感知约束（FOG OF WAR 战争迷雾）
- **为什么这么做**：Token 节省 + 防止 LLM "全知全能"地在叙事中提及远处发生的事

#### 2.5 动态状态过滤（按地理关键词）

```python
# llm_prompting.py:56-94
def _build_scope_keywords(current_node, nearby_nodes, predicted_next):
    # 提取当前/邻近/目标节点名作为关键词
    keys = set()
    for node in {current_node, predicted_next, *nearby_nodes}:
        keys.add(name)
        if name.endswith("内部"): keys.add(name[:-2])  # "东教学楼内部" → "东教学楼"
        if name.endswith("南") or name.endswith("北"): keys.add(name[:-1])

def _filter_dynamic_states(dynamic_states, scope_keywords):
    always_tokens = ("主控", "全校", "警报", "紧急", "皇室令牌", ...)
    for item in rows:
        if any(token in item for token in always_tokens):
            out.append(item)  # 全局重要信息总是可见
        elif any(key in item for key in scope_keywords):
            out.append(item)  # 与当前位置相关的信息才可见
```

- **约束类型**：关键词匹配过滤（不是向量检索，是纯字符串匹配）
- **适用条件**：动态状态列表可能积累数十条，全部注入会爆上下文
- **为什么不用 RAG**：状态条目是结构化短文本，关键词匹配足够精确且零延迟

#### 2.6 触发器提示压缩

```python
# llm_prompting.py:193-206
def _compact_trigger_hints(rows):
    for item in rows:
        hint_text = _first_sentence(...)  # 只取第一句话
        out.append({
            "id": item.get("id"),
            "owner": item.get("owner"),
            "trigger_time": item.get("trigger_time"),
            "hint": hint_text,  # 压缩后的提示
        })
```

- **约束类型**：信息压缩（取第一句摘要）
- **为什么这么做**：触发器的完整文本可能很长，但 LLM 只需要知道"什么时间可能发生什么"的简要提示

#### 2.7 角色卡组按窗口裁剪

```python
# llm_prompting.py:263-281
def _compact_main_player_state(main_state, battle_active):
    # Token optimization: only keep front-N cards in the current valid window.
    rows["card_deck"] = card_deck_raw[:valid_n]
```

- **约束类型**：信息裁剪（只展示可用的前 N 张卡，不展示排队中的卡）
- **为什么这么做**：减少 Token 消耗，且防止 LLM 误以为排队中的卡可以使用

#### 2.8 同伴可发现性过滤

```python
# llm_prompting.py:221-260
def _is_companion_discoverable_for_node(state, node_name, current_time):
    if bool(state.get("in_team", False)):
        return True  # 已在队伍中的始终可见
    home_node = str(state.get("home_node", "")).strip()
    if home_node == "东教学楼北":
        return node in {"东教学楼内部", "东教学楼北"} and 3.0 < float(current_time) < 8.0
    if home_node == "东教学楼内部" and role_type == "event":
        return node == "东教学楼内部" and float(current_time) < 4.0
    return node == home_node
```

- **约束类型**：空间 × 时间复合门控
- **适用场景**：同伴发现只在特定位置+特定时间窗口内才会在 Prompt 中出现
- **设计哲学**：LLM 无法在 Prompt 中看到不可发现的同伴，因此无法让叙事提及不该出现的人

#### 2.9 敌方导演快照注入

```python
# state_snapshot.py:179
"enemy_director": engine.enemy_director.snapshot(),
```

EnemyDirector 的 `snapshot()` 方法向 LLM 提供未来敌方行动的 **有限预览**，让 LLM 在叙事中可以暗示"远处传来爆炸声"之类的氛围描写，但不会暴露完整的敌方行为计划。

---

### Level 2：算法检索注入

本项目 **不使用** 向量检索 / RAG。所有上下文检索都是确定性规则过滤。

### Level 3：大模型主动索取

本项目 **不允许** LLM 主动调用工具获取信息。LLM 只能被动接收系统注入的上下文。

---

## 维度三：效果执行与状态突变（Action Execution & State Mutation）

> "大模型输出后，怎么影响游戏？"

### Level 0：严格参数化调用（Strict API Calling）

#### 3.1 命令块解析

LLM 输出必须使用 `[command]...[/command]` 标签包裹结构化指令：

```python
# llm_agent_bridge.py:22-28
def extract_command_blocks(text):
    pattern = re.compile(r"\[command\](.*?)\[/command\]", re.IGNORECASE | re.DOTALL)
    return [m.strip() for m in pattern.findall(text) if m.strip()]
```

**每条命令的语法严格固定**：

```
<角色名>.move=<节点名>
<角色名>.deploy=<卡牌名>[@<节点名>]
time.advance=<数值>
global.battle=<目标|none>
<角色名>.health=<数值>
scene_event.trigger=<事件ID>
game_event.trigger=<事件ID>
trigger.add=<触发器语句>
companion.<名字>.discovered=true
...
```

- **约束类型**：严格 KV 格式（`left=right` / `left+=right` / `left-=right`）
- **解析失败处理**：命令无法解析时抛异常，记录到 errors 列表，不影响其他命令执行

#### 3.2 命令级别的硬性拦截（LLMAgentBridge）

在 LLM 输出命令被发送到 CommandPipeline 之前，LLMAgentBridge 会进行一层 **硬性过滤**：

```python
# llm_agent_bridge.py:133-214
def _apply_commands(pipeline, commands, applied, errors, source, ...):
    for line in commands:
        # 拦截 1：所有移动命令
        if ".move=" in line:
            errors.append(f"command blocked: {line} -> movement is backend-resolved")
            continue

        # 拦截 2：重试模式下冻结时间/位置/事件
        if freeze_time_position_updates:
            if line.startswith("time.advance"):
                errors.append("blocked -> retry mode freezes time update")
                continue
            if ".location=" in line or ".escape=" in line:
                errors.append("blocked -> retry mode freezes position update")
                continue
            if line.startswith("game_event.trigger=") or line.startswith("scene_event.trigger="):
                errors.append("blocked -> retry mode blocks event triggers")
                continue

        # 拦截 3：事件触发后禁止追加 time.advance
        if event_trigger_applied and line.startswith("time.advance"):
            errors.append("blocked -> event handles time advance automatically")
            continue

        # 拦截 4：nearby_units 必须用增量操作
        if assign_op == "=" and left_key.endswith(".nearby_units"):
            errors.append("blocked -> nearby_units must use += / -=")
            continue

        # 拦截 5：禁止 LLM 删除/清空触发器
        if left_key in {"trigger.remove", "trigger.clear"}:
            errors.append("blocked -> trigger timeline is backend-managed")
            continue

        # 拦截 6：事件 ID 不能是纯数字
        if event_id.isdigit():
            errors.append("blocked -> trigger id must be event name, not number")
            continue

        # 拦截 7：禁止 LLM 修改主控 card_valid
        if main_player and line.startswith(f"{main_player}.card_valid"):
            errors.append("blocked -> card_valid is event-managed")
            continue
```

**被拦截命令的完整清单：**

| 命令 | 拦截原因 | 代码位置 |
|------|---------|---------|
| `*.move=*` | 移动由后端自动处理 | :149-151 |
| `time.advance` (重试模式) | 防止重复结算时间 | :153-155 |
| `*.location=*` (重试模式) | 防止重复结算位置 | :156-158 |
| `*.escape=*` (重试模式) | 同上 | :156-158 |
| `game_event.trigger` (重试模式) | 防止重复触发事件 | :159-161 |
| `scene_event.trigger` (重试模式) | 同上 | :159-161 |
| `time.advance` (事件后) | 事件自带时间推进 | :164-168 |
| `*.nearby_units=*` (全量赋值) | 必须用 `+=/-=` 增量 | :169-173 |
| `trigger.remove` | 时间线由后端管理 | :174-178 |
| `trigger.clear` | 同上 | :174-178 |
| 数字事件 ID | 必须用事件名称 | :179-183 |
| `主控玩家.card_valid` | 由安装/令牌状态管理 | :191-195 |

#### 3.3 自动兜底时间推进

```python
# llm_agent_bridge.py:207-214
# 如果 LLM 忘记输出 time.advance 且没有事件触发：
if allow_time_advance and (not has_time_advance) and (not event_trigger_applied):
    try:
        pipeline.compile_line("time.advance=0.5")
        applied.append("time.advance=0.5")
    except Exception as exc:
        errors.append(f"auto time.advance failed: {exc}")
```

- **约束类型**：兜底保护（防止游戏时间冻结）
- **为什么需要**：LLM 有时会忘记在 `[command]` 块中写 `time.advance`，导致时间永远停滞

#### 3.4 自动队列冲刷

```python
# llm_agent_bridge.py:240-262
def _flush_queue_if_needed(pipeline, commands, ...):
    has_queue_action = any(".deploy=" in line for line in commands)
    has_explicit_flush = any(line.strip() == "queue.flush=true" for line in commands)
    if (not has_queue_action) or has_explicit_flush:
        return
    # LLM 部署了卡但忘记 flush → 自动 flush
    pipeline.compile_line("queue.flush=true")
```

- **约束类型**：兜底保护（确保 deploy 命令实际执行）

---

### Level 1：离散逻辑 + 自由文本（Hybrid Output）

本项目的核心设计就是 **Level 1**：

- **固定逻辑部分**：`[command]...[/command]` 块中的指令，经过严格解析和校验
- **自由文本部分**：`[command]` 块之外的所有叙事文本，直接展示给玩家

```python
# llm_agent_bridge.py:274-288
def _flatten_commands(text):
    blocks = extract_command_blocks(text)
    lines = []
    for block in blocks:
        for raw in block.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                inner = line[1:-1].strip()
                if inner:
                    line = inner
            lines.append(line)
    return lines
```

前端在渲染时会剥离 `[command]` 块：

```typescript
// ChatView.tsx:25-27
const formatText = (text: string) => {
    return text.replace(/\[command\][\s\S]*?\[\/command\]/g, '').trim();
};
```

---

### Level 2：语义状态修改（Semantic State Mutation）

#### 3.5 动态状态标签

LLM 可以通过 `global.state+=<文本>` 向全局动态状态列表添加自然语言标签：

```python
# command_pipeline.py:237-240
def _apply_plus(self, left, right):
    if left == "global.state":
        self.engine.add_global_dynamic_state(right)
        return
```

这些自然语言标签会在后续回合被注入 LLM 上下文，影响叙事走向：

```
global.state+=主控玩家发现了一个隐藏的通道
global.state+=远处传来剧烈的爆炸声
global.state+=颜宏帆对你怒目而视
```

- **约束类型**：自由文本状态标签（语义级状态机）
- **影响链**：LLM 输出 → 标签写入 → 下一轮上下文包含此标签 → 影响 LLM 后续叙事
- **约束条件**：标签只是文本，不直接触发任何硬编码逻辑。但部分标签会被硬编码规则检测（如 `"场景事件:国际部信息老师封锁国际部出口"` 会影响逃跑验证）

#### 3.6 角色历史追加

```python
# command_pipeline.py:245-249
if left.startswith("character.") and left.endswith(".history"):
    name = left[len("character.") : -len(".history")]
    self.engine.add_character_history(name, right)
```

LLM 可以向角色的永久历史记录添加条目（如 `character.颜宏帆.history+=与主角在厕所发生冲突`），这些记录在后续回合会作为上下文注入。

#### 3.7 触发器添加

```python
# command_pipeline.py:407-410
if left == "trigger.add":
    item = self.engine.global_config.add_scripted_trigger(right)
    self.runtime_messages.append(f"trigger added: #{item['id']}")
```

LLM 可以创建未来的脚本化触发器（如 `trigger.add=时间12 若主角在图书馆 则 提示:图书馆传来怪声`），这些触发器在到达指定时间时由 `global_event_checker` 自动执行。

**但 LLM 不能删除/清空触发器**（被 `llm_agent_bridge.py:174-178` 拦截）。

---

## 维度四：大模型的权限作用域（Scope of Agency）

> "这个事件的发生，能撼动游戏世界的哪一层基石？"

### Level 0：表现层 / 装饰性（Cosmetic / Flavor）

#### 4.1 叙事文本生成

LLM 生成的所有 `[command]` 块之外的文本都是纯表现层：

- 环境描写（"寒风呼啸，走廊空无一人"）
- NPC 对话（"罗宾紧张地看着你：'快走！'"）
- 动作描述（"你蹑手蹑脚地走过转角"）
- 氛围渲染（"远处隐约传来爆炸声"）

**特点**：这些文本不写入任何状态机，不影响任何逻辑分支。下一轮 LLM 只能通过 `recent_turns`（最近 6 轮）的历史间接看到之前的叙事。

#### 4.2 角色动态状态标签（叙述性）

通过 `<角色>.state+=<文本>` 添加的角色级标签，如果没有被硬编码规则检测，就是纯装饰性的：

```
颜宏帆.state+=狂笑着逃出教室
罗宾.state+=紧紧跟在你身后
```

### Level 1：局部沙盒 / 实体层（Localized State）

#### 4.3 同伴好感度

```python
# command_pipeline.py:608-610
if field == "affection":
    self.engine.set_companion_affection(name, self._parse_float(right))
```

- **约束范围**：单个同伴实体的 `affection` 字段
- **影响**：好感度影响同伴行为描述（叙事风格），不影响主线进程
- **上限保护**：引擎内部会 clamp 好感度到合理范围

#### 4.4 附近单位状态标签

```python
# command_pipeline.py:528-546
if field == "nearby_unit" and len(left_parts) >= 3:
    role.set_nearby_unit_status(unit_name, self._normalize_nearby_status(right))
```

LLM 可以修改角色身边的叙事性单位状态标签（`full` / `damaged` / `dead`），用于描述 NPC 身边的小兵状况。这些标签不直接影响游戏机制。

#### 4.5 角色血量修改

```python
# command_pipeline.py:506-508
if field == "health":
    self.engine.set_role_health(role_name, self._parse_float(right))
```

LLM 可以修改任何角色的血量，包括设为 0（死亡）。但死亡触发 **硬编码的后果链**：

```python
# engine.py:208-223
def set_role_health(self, role_name, value):
    role.set_health(value)
    if role.health <= 0:
        # 清除该角色拥有的所有单位
        # 移出同伴队伍
        # 通知 enemy_director
        self._check_main_player_game_over()
```

- **约束类型**：LLM 有权修改数值，但后果由硬编码链处理
- **风险控制**：主控死亡 → game_over 由引擎硬编码判定，LLM 不能"复活"

#### 4.6 卡牌部署

LLM 可以通过 `<角色>.deploy=<卡名>` 部署卡牌：

```python
# command_pipeline.py:474-488
if field == "deploy":
    self._assert_role_location_valid_for_internal_action(role_name, "deploy")
    card_name, node_name = self._parse_deploy_payload(right)
    self.message_queue.append(QueueMessage(action="deploy", ...))
```

**约束链**：
1. 角色位置必须有效（所在建筑未被摧毁）
2. 卡牌必须存在于卡库中
3. 部署会扣除圣水（由 `PlayerRole.deploy_from_deck()` 执行）
4. 圣水不足时部署失败（异常被捕获，记录到 errors）
5. 主控的圣水受 `can_main_player_gain_holy_water` 门控

### Level 2：全局核心 / 逻辑分支层（Global Logic）

#### 4.7 战斗状态设置

```python
# command_pipeline.py:385-389
if left == "global.battle":
    battle_target = self._parse_battle_value(right)
    self.engine.set_battle_state(battle_target)
```

LLM 可以发起和结束战斗，这会影响：
- 圣水回复速率（战斗中 2 倍加速）
- 逃跑可用性（战斗中不可逃跑）
- 场景事件可用性（战斗中不展示场景事件）

#### 4.8 场景/游戏事件触发

这是 LLM 能触及的 **最高权限操作**：

```python
# command_pipeline.py:422-429
if left == "scene_event.trigger":
    self._apply_scene_event_trigger(right.strip())
if left == "game_event.trigger":
    self._apply_game_event_trigger(right.strip())
```

但每个事件 ID 都对应一个 **硬编码的处理函数**，有严格的前置条件检查：

| 事件 ID | 效果 | 前置条件 |
|---------|------|---------|
| `opening_borrow_hotspot_handoff` | 马超鹏交手机 + 切换卡组 + 推进 2 时间 | 主控在东教学楼内部, t<5 |
| `install_update_game_with_own_phone` | 游戏安装 + 推进 2 时间 | 手机未被没收 |
| `east_toilet_yanhongfan_encounter` | 发起与颜宏帆的战斗 | 主控在东教学楼内部, 颜宏帆存活, t<5 |
| `international_it_teacher_reveal_confiscate` | 信息老师没收手机 + 封锁出口 | 主控在国际部, 信息老师存活 |
| `destroy_dezheng_blue_device_with_heavy` | 摧毁蓝光装置（可能引爆德政楼） | 主控在德政楼, 有重型单位 |
| `break_gate_guard_blockade_with_units` | 突破保安防线 | 主控在正门/后门, 有足够攻击力单位 |
| `canteen_liqinbin_remind_and_token` | 获得皇室令牌（card_valid 8→8） | 主控在食堂 |
| `lzb_trigger_dezheng_device_blast` | 李再斌引爆德政楼 | 特定条件 |

**约束类型**：LLM 只能请求触发预定义事件，不能创建新事件类型。每个事件都有硬编码的条件检查和效果链。

#### 4.9 建筑摧毁（通过触发器/事件）

LLM 可以通过 `event.rocket_launch=<建筑>` 创建延迟坍塌触发器：

```python
# command_pipeline.py:430-441
if left == "event.rocket_launch":
    trigger_text = f"角色:系统|时间{now + 1:g} 若火箭命中{target} 则 建筑倒塌:{target}"
    item = self.engine.global_config.add_scripted_trigger(trigger_text)
```

建筑坍塌的后果链：

```python
# global_event_checker.py:264-293
def _apply_structure_collapse(self, target, now):
    affected_nodes = self._resolve_collapse_nodes(target)
    for node_name in affected_nodes:
        self.engine.set_node_valid(node_name, False)     # 节点失效
    for role_name in sorted(affected_roles):
        if self._is_role_protected_from_collapse(target, role_name):
            continue  # 特殊豁免（如黎诺存在西教学楼坍塌时豁免）
        self.engine.set_role_health(role_name, 0)        # 击杀在场角色
    if "德政楼" in affected_nodes:
        self._trigger_emergency(now)                      # 德政楼→紧急状态
```

**特殊保护规则**：

```python
# global_event_checker.py:295-301
@staticmethod
def _is_role_protected_from_collapse(target, role_name):
    # 黎诺存在西教学楼坍塌链路中豁免（保留后续火箭主线）
    if role_name == "黎诺存" and target in ("西教学楼", "西教学楼南", "西教学楼北"):
        return True
    return False
```

- **约束类型**：LLM 可以发起全局级别的状态突变（建筑摧毁 → 角色死亡 → 紧急状态 → 爆炸倒计时），但效果链的每一步都是硬编码的

---

## 约束类型总结表

| 约束类型 | 描述 | 代码位置 | 触发-上下文-执行-作用域 |
|---------|------|---------|-------------------|
| **时间阈值硬门槛** | t>8→警报, t≥爆炸时间→全灭 | `global_event_checker.py` | L0-L1-L0-L2 |
| **数值钳制** | 圣水[0,10], 时间[0,100], 卡组恒为8张 | `engine.py`, `roles.py` | -\--L0-L1 |
| **空间邻接校验** | 移动只能到相邻节点 | `engine.py:130-133` | L0-\--L0-L1 |
| **安装状态门控** | 未安装游戏→圣水强制0, card_valid强制0 | `engine.py:243-245` | L0-L1-L0-L1 |
| **命令格式约束** | 必须 `[command]...[/command]` + `left=right` | `llm_agent_bridge.py` | -\--L0-\- |
| **命令黑名单** | 移动/trigger.remove/card_valid 被拦截 | `llm_agent_bridge.py:146-198` | -\--L0-\- |
| **重试冻结** | 重试模式下禁止时间/位置/事件更新 | `llm_agent_bridge.py:152-161` | L0-\--L0-\- |
| **兜底时间推进** | LLM忘记time.advance时自动+0.5 | `llm_agent_bridge.py:207-214` | -\--L0-L1 |
| **感知范围过滤** | 只注入当前+邻近节点的信息 | `llm_prompting.py`, `state_snapshot.py` | -L1+-\--\- |
| **动态状态过滤** | 按地理关键词过滤dynamic_states | `llm_prompting.py:70-94` | -L1+-\--\- |
| **触发器压缩** | 只取第一句摘要 | `llm_prompting.py:193-206` | -L1+-\--\- |
| **同伴可见性门控** | 位置×时间决定是否在Prompt中出现 | `llm_prompting.py:221-260` | L0-L1-\--\- |
| **事件前置条件** | 每个scene/game事件都有硬编码检查 | `command_pipeline.py:739-989` | L1-\--L0-L2 |
| **坍塌豁免** | 黎诺存在西教学楼坍塌时豁免 | `global_event_checker.py:295-301` | L0-\--L0-L2 |
| **敌方行为固定** | 3个敌对角色行为全部预编写 | `enemy_director.py` | L0-\--L0-L2 |
| **语义状态标签** | LLM通过global.state+=写入文本标签 | `command_pipeline.py:237-240` | -\--L2-L0/L1 |
| **触发器创建** | LLM可创建未来触发器 | `command_pipeline.py:407-410` | -\--L2-L1/L2 |

---

## 整体设计哲学

### 1. "硬骨架 + 软血肉"

- **硬骨架**：时间线、建筑坍塌链、敌方行为计划、游戏结束条件——全部硬编码
- **软血肉**：叙事文本、对话内容、氛围描写、分支选择的措辞——交给 LLM

### 2. "先算后问"

- 在调用 LLM 之前，后端已经完成了自动移动、失败命令重试、状态同步
- LLM 输出后，后端再进行命令过滤、校验、兜底
- LLM 永远工作在两层硬编码"保护壳"之间

### 3. "有限权限 + 无限表达"

- LLM **不能**：移动主控、修改 card_valid、删除触发器、创建新事件类型
- LLM **可以**：部署卡牌、设置血量、发起战斗、创建触发器、写入语义状态标签、生成任意叙事文本

### 4. "上下文即权限"

- LLM 看不到远处角色的详细信息 → 无法在叙事中精确描述远处发生的事
- LLM 看不到不可发现的同伴 → 无法让叙事提及还未出现的人
- LLM 看不到排队中的卡牌 → 不会误用不可用的卡

### 5. "单向因果链"

触发器的设计体现了严格的单向因果：

```
LLM 创建触发器（trigger.add）
     ↓
时间推进到触发时间
     ↓
global_event_checker 检查条件
     ↓ (条件满足)
执行硬编码结果（提示/建筑倒塌/角色死亡）
     ↓
LLM 在下一轮看到结果（通过 dynamic_states 注入）
```

LLM 可以创建触发器，但不能阻止已创建的触发器执行（trigger.remove 被拦截）。这确保了"言出必行"的叙事一致性。

---

## 完整请求处理流程图

```
玩家输入 "向西走"
      │
      ▼
[app.py] 会话/游戏状态校验 ──────── Level 0 硬编码门控
      │
      ▼
[app.py] _try_auto_apply_main_move() ── Level 0 关键词匹配+邻接校验
      │  成功：后端直接执行移动+时间推进
      │  失败：跳过，交给 LLM
      │
      ▼
[app.py] _apply_pending_retries() ──── 重试失败命令
      │
      ▼
[state_snapshot.py] build_step_context() ── Level 1+ 规则过滤注入
      │  - 感知范围裁剪
      │  - 动态状态按关键词过滤
      │  - 触发器压缩
      │  - 同伴可见性门控
      │  - 敌方快照注入
      │
      ▼
[llm_prompting.py] build_narrative_prompt() ── 组装最终 Prompt
      │
      ▼
[LLM API] 流式生成 ──────────────── 消耗 Token
      │
      ▼
[llm_agent_bridge.py] 流式输出 + 命令提取
      │  - 叙事 chunk → 直接推送前端
      │  - thinking tick → 推送前端
      │  - [command] 块 → 提取命令列表
      │
      ▼
[llm_agent_bridge.py] _apply_commands() ── Level 0 命令过滤
      │  - 拦截黑名单命令
      │  - 重试模式冻结
      │  - 兜底 time.advance
      │
      ▼
[command_pipeline.py] compile_line() ── Level 0 命令执行
      │  - 语法校验
      │  - 场景/游戏事件硬编码处理
      │  - 队列管理
      │
      ▼
[engine.py] advance_time() ──────── Level 0 硬编码状态更新
      │  - 推进移动任务
      │  - 圣水回复
      │  - 同伴自动检查
      │  - 敌方导演推进
      │  - 触发器检查
      │  - 主控死亡检查
      │  - 运行时门控同步
      │
      ▼
[app.py] _get_player_state() → 推送最终状态到前端
```
