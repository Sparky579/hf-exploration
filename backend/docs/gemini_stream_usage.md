# Gemini 流式调用说明

## 1. 设置 API Key
建议使用环境变量，不要把 key 写入代码：

```powershell
$env:GOOGLE_API_KEY="你的key"
```

## 2. 运行流式演示

```powershell
python backend/scripts/gemini_stream_demo.py --model gemini-3-flash-preview --apply-commands
```

可选参数：
- `--api-key`：命令行传 key（不推荐）。
- `--input`：本轮用户输入文本。
- `--model`：模型名，默认 `gemini-3-flash-preview`。
- `--apply-commands`：解析并执行模型返回的 `[command]` 命令。

## 3. 输出结构
脚本会输出：
1. 流式剧情文本（实时打印）。
2. 解析出的叙事命令。
3. 解析出的旁角色懒更新命令。
4. 命令应用结果与失败信息。
