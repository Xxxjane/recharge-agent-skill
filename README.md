# 虚拟商品代充值 AI Agent Skill (Plugin)

> 一个严格遵循业务 PRD 的虚拟商品代充值独立插件（Skill/Tool），专为 AI Agent 框架设计。

通过统一的 OpenAPI 契约 + 强约束 System Prompt，让 AI Agent 能够安全、合规地引导用户完成「品牌选择 → 级联规格 → 账号校验 → 红灯泡二次确认 → 下单支付 → 履约监控」全流程。

---

## ✨ 核心特性

- **严格业务规则落地**
  - 单次交易强制 `quantity = 1`（防刷 + 防错）
  - 充值账号必须通过品牌模板 `inputRegex` 校验
  - 强制 `X-Idempotency-Key` 幂等防重，杜绝重复扣款
- **15 分钟履约大闸 + 自动退款**
  - 支付成功后启动异步定时器
  - 超时未发货自动流转 `REFUNDED` 并记录日志
  - 支持 `DEBUG_MODE` 将 15 分钟加速为 15 秒（便于本地调试）
- **完整级联 SKU 模板**
  - 支持「一级规格（会员类型/币种）→ 二级规格（时长/面额）」动态级联
  - 实时返回全网最优价 `bestPrice`
- **红灯泡二次确认机制**
  - Prompt 强制 Agent 在下单前输出醒目确认框
  - 必须用户明确“确认”后才能调用创建订单接口
- **开箱即用的集成配置**
  - 提供 Dify 自定义工具配置 (`integration/dify/tool_config.json`)
  - 提供 Coze（扣子）插件元数据 (`integration/coze/metadata.json`)
- **完整自动化测试**
  - `test_skill.py` 覆盖异常流、正常流、幂等流、超时退款全场景

---

## 🏗️ 系统架构

```
                    ┌─────────────────────────┐
                    │  AI Agent 智能充值助手   │
                    └────────────┬────────────┘
         ┌───────────────────────┴───────────────────────┐
         ▼ (调用 API)                                    ▼ (调用 API)
┌──────────────────┐                            ┌──────────────────┐
│   买家侧 (交易)  │                            │  卖家侧 (履约)   │
│ - 品牌与模板获取 │                            │ - 接收派单通知   │
│ - 账号级联校验   │                            │ - 接单/响应充值  │
│ - 确认下单与支付 │                            │ - 上传凭证/发货  │
└──────────────────┘                            └──────────────────┘
```

- **买家侧**：由彩贝壳 / Jiigo 买家域的 AI 助手驱动，负责交互式引导 + 资金安全。
- **卖家侧**：由 Jiigo 副业助手驱动，负责 15 分钟内履约提醒与凭证上传。

---

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/your-org/recharge-agent-skill.git
cd recharge-agent-skill
```

### 2. 启动 Mock 服务（本地开发 / 调试）

```bash
cd src
pip install fastapi uvicorn pydantic
python app.py
# 或
uvicorn app:app --reload --port 8000
```

服务默认监听 `http://localhost:8000`

### 3. 运行自动化测试

```bash
pip install requests
python test_skill.py
```

测试脚本会自动执行 5 个核心场景（异常拦截、正常下单、幂等性、15 秒自动退款）。

---

## 📡 API 接口概览

完整契约请查看 `[src/schemas/openapi.yaml](src/schemas/openapi.yaml)`


| 方法   | 路径                                   | 说明                   | 关键约束                                         |
| ---- | ------------------------------------ | -------------------- | -------------------------------------------- |
| GET  | `/brands`                            | 获取支持的充值品牌列表          | -                                            |
| GET  | `/brands/{brandId}/template`         | 获取级联 SKU 模板 + 账号校验正则 | 必须先调此接口                                      |
| POST | `/orders/create`                     | 创建待支付代充订单            | 必须传 `X-Idempotency-Key`，`quantity=1`，账号需通过正则 |
| GET  | `/orders/{orderId}/status`           | 查询订单实时状态             | 支付后建议 5~10s 轮询                               |
| POST | `/orders/{orderId}/mock-pay-success` | 【调试】模拟支付成功           | 触发 15 秒（DEBUG）退款计时器                          |
| POST | `/orders/{orderId}/mock-deliver`     | 【调试】模拟卖家发货           | 状态变为 DELIVERED 并返回凭证图                        |


---

## 🧪 自动化测试

项目提供结构化的端到端测试脚本 `test_skill.py`，覆盖：

- Case 1：quantity=2 → 400 拦截
- Case 2：非法账号格式 → 400 拦截
- Case 3：合规下单成功
- Case 4：相同幂等键返回相同订单
- Case 5：DEBUG 模式下 15 秒自动退款（RECHARGING → REFUNDED）

---

## 🔌 Agent 平台集成

### Dify

1. 在 Dify 自定义工具中导入 `integration/dify/tool_config.json`
2. 将 `src/prompt/system_prompt.md` 内容作为 System Instruction 注入
3. 在对话中测试“帮我充腾讯视频白金会员 3 个月”

### Coze（扣子）

1. 在 Coze 插件市场或自定义插件中导入 `integration/coze/metadata.json`
2. 启用图片卡片能力，订单状态变为 `DELIVERED` 时可直接渲染 `rechargeProofUrl`
3. 建议在工作流中配置轮询节点 + 图片卡片展示节点

---

## ☁️ 部署指南

详细部署步骤请参考：

- [docs/Deployment_Guide.md](docs/Deployment_Guide.md)

支持一键部署到：

- Vercel
- Render
- Zeabur
- Railway / Docker 等

---

## 📖 业务背景

本项目完整还原了 **Jiigo × 彩贝壳** 虚拟商品代充业务的核心商业闭环。

详细产品规则、双边角色、15 分钟履约机制、自动收货逻辑请阅读：

- [docs/PRD_Reference.md](docs/PRD_Reference.md)

---

## 📁 项目结构

```
recharge-agent-skill/
├── .github/workflows/          # CI/CD 配置（待完善）
├── docs/
│   ├── Deployment_Guide.md     # 部署指南
│   └── PRD_Reference.md        # 产品 PRD 参考
├── src/
│   ├── app.py                  # FastAPI Mock 服务（核心）
│   ├── prompt/
│   │   └── system_prompt.md    # AI Agent 核心约束 Prompt
│   └── schemas/
│       └── openapi.yaml        # OpenAPI 3.0 标准契约
├── integration/
│   ├── dify/tool_config.json   # Dify 工具配置
│   └── coze/metadata.json      # Coze 插件元数据
├── test_skill.py               # 自动化测试脚本
└── README.md
```

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

建议流程：

1. 先阅读 `docs/PRD_Reference.md` 理解业务规则
2. 修改 `src/schemas/openapi.yaml` 时同步更新 Prompt 与测试
3. 新增功能请补充对应测试用例

---

## 📄 License

MIT License

---

**让 AI Agent 真正懂业务、守规则、走得通闭环。**

如有任何问题，欢迎在 Issues 中讨论。