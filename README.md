# 虚拟商品代充值 AI Agent Skill

> 通用型 Agent Skill：OpenAPI + MCP + Prompt + 渠道 Adapter

让任意 AI Agent（Cursor、Dify、Coze、自研 Bot）安全引导用户完成：**品牌选择 → 级联规格 → 账号校验 → 红灯泡确认 → 支付 → 履约监控**；并支持卖家侧接单履约。

[![CI](https://github.com/Xxxjane/recharge-agent-skill/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/Xxxjane/recharge-agent-skill/actions)

**仓库地址：** https://github.com/Xxxjane/recharge-agent-skill


---

## 特性

- **买家侧 4 工具 + 卖家侧 4 工具**，完整订单状态机
- **业务硬约束**：`quantity=1`、账号正则、`unitPrice=bestPrice`、幂等键、支付/履约超时分离
- **三种接入方式**：OpenAPI（Dify/Coze）、MCP Server（Cursor/Claude）、Cursor SKILL.md
- **渠道 Adapter stub**：微信 / 支付宝 / 美团（可渐进替换 Mock 支付）
- **9 条自动化测试**，覆盖异常流、完整履约、自动/手动确认收货

---

## 架构

```
Agent 层          Cursor / Dify / Coze / 微信 Bot
       ↓                ↓              ↓
通用 Skill 层     MCP Server    OpenAPI REST    SKILL.md
       ↓                └──────┬───────┘
Mock / 真实 API   FastAPI (买家 + 卖家)
       ↓
渠道 Adapter      WeChat / Alipay / Meituan (stub)
```

---

## 快速开始

```bash
git clone https://github.com/Xxxjane/recharge-agent-skill.git
cd recharge-agent-skill
pip install -r requirements.txt
cp .env.example .env

# 启动 Mock API
uvicorn src.app:app --host 127.0.0.1 --port 8000

# 另开终端运行测试
python test_skill.py
```

Docker:

```bash
docker build -t recharge-agent-skill .
docker run -p 8000:8000 -e DEBUG_MODE=true recharge-agent-skill
```

---

## 接入方式

| 方式 | 文档 |
|------|------|
| **OpenAPI / Dify / Coze** | [integration/dify/](integration/dify/) · [integration/coze/](integration/coze/) |
| **MCP（推荐通用接入）** | [integration/mcp/README.md](integration/mcp/README.md) |
| **Cursor Agent Skill** | [.cursor/skills/virtual-recharge/SKILL.md](.cursor/skills/virtual-recharge/SKILL.md) |

---

## API 概览

### 买家侧

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/brands` | 品牌列表 |
| GET | `/brands/{brandId}/template` | 级联模板 + bestPrice |
| POST | `/orders/create` | 创建订单（需 `X-Idempotency-Key`） |
| GET | `/orders/{orderId}/status` | 轮询状态 |
| POST | `/orders/{orderId}/confirm-receipt` | 确认收货 |

### 卖家侧

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/seller/orders/pending` | 待履约列表 |
| POST | `/seller/orders/{orderId}/accept` | 接单 |
| POST | `/seller/orders/{orderId}/start-recharge` | 开始充值 |
| POST | `/seller/orders/{orderId}/deliver` | 上传凭证发货 |

完整契约：[src/schemas/openapi.yaml](src/schemas/openapi.yaml)

---

## 项目结构

```
recharge-agent-skill/
├── .cursor/skills/virtual-recharge/SKILL.md
├── .github/workflows/ci-cd.yml
├── adapters/              # 微信/支付宝/美团 stub
├── docs/
│   ├── PRD_Reference.md
│   ├── Deployment_Guide.md
│   ├── Development_Guide.md
│   └── Agent_Skill_Spec.md
├── examples/
├── integration/           # Dify / Coze / MCP
├── recharge_mcp/          # MCP Server
├── src/
│   ├── app.py
│   ├── config.py
│   ├── prompt/
│   └── schemas/
├── test_skill.py
├── Dockerfile
├── LICENSE
└── requirements.txt
```

---

## 业务背景

---

## 已知限制（Mock 阶段）

- **支付**：`payUrl` 为 Mock 链接，非真实微信/支付宝收银台
- **存储**：订单数据在内存中，服务重启后丢失
- **渠道 Adapter**：`adapters/` 下微信/支付宝/美团为接口 stub，需自行接入 SDK
- **集成配置**：Dify/Coze 的 `base_url` 默认为占位地址，部署后请改为 `http://127.0.0.1:8000` 或你的云部署 URL

---

## 贡献

详见 [CONTRIBUTING.md](CONTRIBUTING.md)

1. 阅读 PRD 与 OpenAPI
2. 修改 API 时同步 Prompt、integration 配置与测试
3. `python test_skill.py` 必须通过

---

## License

MIT — see [LICENSE](LICENSE)
