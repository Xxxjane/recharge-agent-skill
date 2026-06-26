# 部署指南

本指南帮助开发者将 `recharge-agent-skill` 的 Mock 服务部署到主流云平台，便于团队联调、演示和生产环境验证。

> 服务基于 **FastAPI + Uvicorn** 实现，推荐使用 Python 3.9+。

---

## 0. Docker 一键部署（推荐）

```bash
docker build -t recharge-agent-skill .
docker run -p 8000:8000 -e DEBUG_MODE=false recharge-agent-skill
```

访问 `http://localhost:8000/docs` 查看 Swagger。

---

## 📋 部署前准备

1. 确认代码已克隆到本地
2. 安装依赖：
  ```bash
   pip install -r requirements.txt
  ```
3. 本地先跑通：
  ```bash
   uvicorn src.app:app --host 0.0.0.0 --port 8000
   # 访问 http://localhost:8000/docs 查看 Swagger
  ```

---

## 1. 部署到 Vercel

Vercel 原生支持 Python Serverless Function，但对 FastAPI 支持需要额外配置。

### 推荐方式：使用 `vercel-python` 适配

**步骤：**

1. 在项目根目录创建 `vercel.json`：

```json
{
  "version": 2,
  "builds": [
    {
      "src": "src/app.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "src/app.py"
    }
  ]
}
```

1. 在 `src/app.py` 底部添加 Vercel 需要的 handler（可选但推荐）：

```python
# Vercel Serverless 需要暴露 app 对象
# 已有 if __name__ == "__main__": 部分无需修改
```

1. 安装 Vercel CLI 并部署：

```bash
npm i -g vercel
vercel
# 或
vercel --prod
```

1. 部署完成后，Vercel 会给出类似 `https://xxx.vercel.app` 的地址。

**注意事项：**

- Vercel Serverless 有 10 秒执行限制，长时间轮询可能受影响。
- 内存中的定时器（`asyncio.create_task`）在 Serverless 环境下可能无法可靠运行，建议仅用于演示。
- 生产环境建议配合外部定时任务或数据库持久化状态。

---

## 2. 部署到 Render

Render 对 Python Web 服务支持极好，且免费额度友好。

**步骤：**

1. 登录 [Render](https://render.com)
2. 点击 **New +** → **Web Service**
3. 连接你的 GitHub 仓库
4. 配置参数：
  - **Name**: `recharge-agent-skill-mock`
  - **Environment**: `Python 3`
  - **Build Command**: `pip install -r requirements.txt`
  - **Start Command**: `cd src && uvicorn app:app --host 0.0.0.0 --port $PORT`
  - **Instance Type**: Free（或 Starter）
5. 在项目根目录创建 `requirements.txt`（如果还没有）：

```txt
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
pydantic>=2.6.0
```

1. 点击 **Create Web Service**

部署完成后，Render 会提供 `https://xxx.onrender.com` 地址。

**健康检查**：可在服务设置中添加 `/brands` 作为健康检查路径。

---

## 3. 部署到 Zeabur

Zeabur 是国内开发者常用的平台，支持一键部署且对中文用户体验较好。

**步骤：**

1. 访问 [Zeabur](https://zeabur.com)
2. 使用 GitHub 授权登录
3. 点击 **New Project** → 选择你的仓库
4. Zeabur 会自动识别 Python 项目
5. 在服务设置中配置：
  - **Root Directory**: `src` （或保持根目录）
  - **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
  - **Build Command**: `pip install -r requirements.txt`
6. 添加环境变量（可选）：
  - `DEBUG_MODE=true`
7. 点击部署

Zeabur 会自动分配域名，如 `xxx.zeabur.app`。

**优势**：国内访问速度快、支持自定义域名、自动 HTTPS。

---

## 4. 使用 Docker 部署（通用方案）

### Dockerfile 示例

在项目根目录创建 `Dockerfile`：

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

EXPOSE 8000

CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

`requirements.txt` 同上。

### 构建与运行

```bash
docker build -t recharge-skill-mock .
docker run -p 8000:8000 recharge-skill-mock
```

### 部署到支持 Docker 的平台

- **Railway**
- **Zeabur**（支持 Dockerfile）
- **阿里云 / 腾讯云容器服务**
- **Fly.io**

---

## 5. 环境变量与配置建议


| 变量名          | 默认值    | 说明              | 建议               |
| ------------ | ------ | --------------- | ---------------- |
| `DEBUG_MODE` | `true` | 是否开启调试加速（15秒退款） | 生产环境建议设为 `false` |
| `PORT`       | `8000` | 云平台通常通过环境变量注入   | 无需手动设置           |


在 `app.py` 中已读取 `DEBUG_MODE`，可通过平台环境变量覆盖（需在代码中增加 `os.getenv` 支持，建议后续增强）。

---

## 6. 部署后验证

部署成功后，建议执行以下检查：

1. 访问 `https://your-domain.com/brands` → 应返回两个品牌
2. 访问 `https://your-domain.com/docs` → 应看到 Swagger UI
3. 运行修改后的测试脚本（把 `BASE_URL` 改成你的域名）：
  ```python
   BASE_URL = "https://your-domain.com"
  ```
4. 测试完整闭环：
  - 创建订单
  - 调用 `/mock-pay-success`
  - 等待 15 秒（DEBUG 模式）
  - 轮询状态变为 `REFUNDED`

---

## 7. 生产环境建议

- 将内存存储（`orders`, `idempotency_cache`）迁移到 Redis / 数据库
- 异步退款逻辑改用 **Celery + Beat** 或云平台定时任务
- 关闭 `DEBUG_MODE`
- 添加 API 鉴权（JWT / API Key）
- 配置日志收集与监控（Sentry / Datadog）
- 开启 HTTPS + 自定义域名

---

## 常见问题

**Q: 部署后定时器不生效？**  
A: Serverless 平台通常会冻结容器，`asyncio.create_task` 无法持续运行。建议仅用于演示，生产环境需持久化方案。

**Q: 如何修改端口？**  
A: 大部分平台通过 `$PORT` 环境变量自动注入，无需修改代码。

**Q: 支持热重载吗？**  
A: 生产环境建议关闭 `--reload`，仅本地开发使用。

---

部署完成后，欢迎在项目 Issues 中分享你的部署地址，供社区参考！

如遇到平台特定问题，也欢迎提交 PR 补充本指南。