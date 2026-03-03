# HF-Explore

这是一款校园生存/探险类游戏。包含基于 FastAPI 构建的后端，以及基于 React + Vite 构建的前端。

## 环境要求

- **Python 3.8+**（后端环境）
- **Node.js**（前端运行环境，建议使用最新的 LTS 版本）
- **大模型 API Key**（Gemini 或 OpenAI）

---

## 1. 后端运行指南 (Backend)

后端主要负责处理游戏的核心逻辑、状态存档以及与 LLM 的交互。

### 运行步骤

1. **打开终端并进入项目根目录：**
   ```bash
   cd "E:\Program Files (x86)\hf-explore"
   ```

2. **配置虚拟环境（推荐）：**
   ```bash
   python -m venv venv
   .\venv\Scripts\activate   # Windows 上激活虚拟环境
   ```

3. **安装依赖：**
   确保你安装了 FastAPI 与 Uvicorn 等核心组件（如果后续加入了 `requirements.txt` 请使用 `pip install -r requirements.txt`）：
   ```bash
   pip install fastapi uvicorn pydantic
   ```

4. **配置环境变量：**
   启动应用前，需要在终端中配置你的 AI 模型密钥：
   ```bash
   # 如果使用 Gemini
   set GOOGLE_API_KEY=你的_API_KEY
   
   # 或者如果使用 OpenAI
   set OPENAI_API_KEY=你的_API_KEY
   ```

5. **启动后端服务：**
   由于代码模块按照 `backend.*` 形式引入，请务必在**项目根目录**（而不是 `backend` 目录）下运行以下命令：
   ```bash
   uvicorn backend.app:app --reload
   ```
   **注意：** `--reload` 表示在代码更改时自动重启服务，方便调试。
   服务默认将在 `http://127.0.0.1:8000` 上启动。

---

## 2. 前端运行指南 (Frontend)

前端负责游戏画面的呈现、用户的操作以及与后端 API 通信，页面采用 React + Vite + Tailwind CSS 构建。

### 运行步骤

1. **重新打开一个新的终端窗口，进入 frontend 文件夹：**
   ```bash
   cd "E:\Program Files (x86)\hf-explore\frontend"
   ```

2. **安装前端所需依赖：**
   ```bash
   npm install
   ```

3. **启动前端开发服务器：**
   ```bash
   npm run dev
   ```
   启动成功后，终端会打印出一个本地域名地址，类似：
   > `http://localhost:5173/`

4. **体验游戏：**
   在浏览器中打开上述地址，即可加载前端页面并与后端开始交互。

---

## 常见问题排查

- **后端的 `backend` 模块找不到？** 
  检查你是否在 `E:\Program Files (x86)\hf-explore` 目录下执行的 `uvicorn backend.app:app`。如果先进入了 `backend` 文件夹，将会抛出 `ModuleNotFoundError`。
- **前端页面中无法响应或报错？**
  1. 检查后端终端窗口是否报错或者被意外终止。
  2. 检查发起请求前是否在后端终端设置了 `GOOGLE_API_KEY` 或 `OPENAI_API_KEY`。
