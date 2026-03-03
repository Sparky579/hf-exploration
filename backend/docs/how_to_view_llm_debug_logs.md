# 如何查看发送给大模型的完整信息

## 结论
后端现在会把每一轮“发给模型的信息 + 模型返回 + 执行结果”完整落日志。

## 日志存储位置
每个会话一个 JSONL 文件：
- `backend/logs/<session_id>.jsonl`

会话创建时，路径会保存在 session 字段 `debug_log_file`。

## API 查看方式
调用：
- `GET /api/logs/{session_id}`

返回包含：
1. `debug_log_file`：本会话日志文件路径
2. `debug_log_entries`：该文件全部日志条目（不截断）
3. 兼容字段：`llm_logs`、`pipeline_logs`、`roles` 等

## 每轮关键字段（round_final）
`debug_log_entries` 中 `type=round_final` 的记录包含：
1. `recent_turns_for_model`：发给模型前的完整对话窗口
2. `backend_step_notes`：后端预执行/重试说明
3. `narrative_prompt`：完整主提示词（全文）
4. `step_context`：构建提示词时使用的完整上下文对象
5. `final_packet`：桥接层完整返回包
6. `model_output`：模型正文输出
7. `narrative_commands`：解析出的命令
8. `applied_commands`：实际执行命令
9. `errors`：命令执行错误
10. `state`：本轮结束后的玩家状态

## 其它日志类型
1. `first_round_fixed`：首轮写死返回（不调用模型）
2. `round_stream_exception`：流式中断异常
3. `round_missing_final_packet`：缺失 final 包

## 说明
1. 已去掉 `260` 字符截断，恢复全量记录。
2. 如果日志体积很大，建议按 `session_id` 定期归档 `backend/logs/`。

