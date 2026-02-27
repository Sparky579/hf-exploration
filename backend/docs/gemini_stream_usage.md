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
- `--input`：本轮用户输入。
- `--model`：模型名，默认 `gemini-3-flash-preview`。
- `--apply-commands`：解析并执行模型返回的命令。

## 3. 线程说明
- 主线线程：流式输出剧情 + 主控命令。
- 隐藏线程：只处理敌对角色 trigger（初始化与触发执行）。

## 4. 输出结构
脚本会输出：
1. 流式剧情文本。
2. 叙事命令解析结果。
3. 敌对 trigger 处理命令解析结果。
4. 命令应用成功/失败列表。
