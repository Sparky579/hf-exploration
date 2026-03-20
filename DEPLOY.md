# HF-Exploration 部署指南

## 端口分配

| 服务 | 端口 | 说明 |
|------|------|------|
| Backend (FastAPI) | 14201 | 后端 API 服务 |
| Frontend (Vite + React) | 14202 | 前端开发服务器 |

## 公网域名

- **前端**: https://hf.sparky.qzz.io （通过 Cloudflare Tunnel 代理到 `127.0.0.1:14202`）

---

## 一键启动

在项目根目录 `/home/sizhe/hf-exploration` 下执行：

```bash
# 1. 启动后端（需要先配置 API Key）
cd /home/sizhe/hf-exploration
source venv/bin/activate
export GOOGLE_API_KEY=你的_API_KEY    # 或 OPENAI_API_KEY
nohup uvicorn backend.app:app --host 0.0.0.0 --port 14201 > backend.log 2>&1 &

# 2. 启动前端
cd /home/sizhe/hf-exploration/frontend
nohup npm run dev -- --host 0.0.0.0 --port 14202 > frontend.log 2>&1 &
```

## 前端配置

前端通过环境变量 `VITE_API_BASE` 指向后端。已在 `frontend/.env` 中配置：

```
VITE_API_BASE=http://localhost:14201/api
```

> **注意**: 如果后端部署到公网，需要把 `localhost:14201` 改为后端的公网地址。

---

## Cloudflare Tunnel 配置

使用的 Tunnel: **meta-analysis-tunnel** (`68994821-005f-4227-a98a-391d89a2c846`)

配置文件: `~/.cloudflared/config.yml`

已添加的 ingress 规则：

```yaml
  # HF Explore
  - hostname: hf.sparky.qzz.io
    service: http://127.0.0.1:14202
```

### DNS 路由

首次需要创建 DNS CNAME 记录（只需执行一次）：

```bash
cloudflared tunnel route dns 68994821-005f-4227-a98a-391d89a2c846 hf.sparky.qzz.io
```

### 启动/重启 Tunnel

```bash
# 停掉旧的 meta-analysis-tunnel（如果有）
pkill -f "cloudflared .* meta-analysis-tunnel"

# 启动
nohup /usr/bin/cloudflared tunnel --config /home/sizhe/.cloudflared/config.yml run meta-analysis-tunnel > /home/sizhe/.cloudflared/meta_tunnel.log 2>&1 &
```

---

## 停止服务

```bash
# 停止后端
pkill -f "uvicorn backend.app:app.*14201"

# 停止前端
pkill -f "vite.*14202"
```

---

## 首次部署（从零开始）

```bash
# 1. 克隆项目
cd /home/sizhe
git clone git@github.com:Sparky579/hf-exploration.git
cd hf-exploration

# 2. 后端：创建虚拟环境并安装依赖
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn pydantic

# 3. 前端：安装依赖
cd frontend
npm install

# 4. Cloudflare DNS 路由（只需一次）
cloudflared tunnel route dns 68994821-005f-4227-a98a-391d89a2c846 hf.sparky.qzz.io

# 5. 在 ~/.cloudflared/config.yml 的 ingress 中添加：
#   - hostname: hf.sparky.qzz.io
#     service: http://127.0.0.1:14202

# 6. 然后按上面的「一键启动」步骤启动所有服务
```
