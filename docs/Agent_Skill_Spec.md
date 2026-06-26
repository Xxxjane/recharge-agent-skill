# 虚拟商品代充值 Agent Skill 规范

本规范将 Jiigo × 彩贝壳「虚拟商品代充值」PRD 转换为通用 AI Agent 插件标准。

## 系统拓扑

- **买家侧**：品牌/模板 → 级联选择 → 账号校验 → 红灯泡确认 → 下单支付 → 状态轮询
- **卖家侧**：待履约列表 → 接单 → 开始充值 → 上传凭证发货

## 权威契约

- OpenAPI：[src/schemas/openapi.yaml](../src/schemas/openapi.yaml)
- 买家 Prompt：[src/prompt/system_prompt.md](../src/prompt/system_prompt.md)
- 卖家 Prompt：[src/prompt/seller_prompt.md](../src/prompt/seller_prompt.md)

## 接入方式


| 方式                 | 路径                                         |
| ------------------ | ------------------------------------------ |
| REST / Dify / Coze | `integration/`                             |
| MCP                | `recharge_mcp/server.py`                   |
| Cursor Skill       | `.cursor/skills/virtual-recharge/SKILL.md` |
| 渠道 Adapter         | `adapters/`                                |


## 核心约束

1. `quantity` 恒等于 1
2. `unitPrice` 必须等于模板 `bestPrice`
3. 下单前必须红灯泡二次确认（Prompt）
4. 支付超时 30 分钟 → `CLOSED`；履约超时 15 分钟 → `REFUNDED`
5. 发货后次日 23:59:59 自动确认收货 → `COMPLETED`

详细业务规则见 [PRD_Reference.md](PRD_Reference.md)。