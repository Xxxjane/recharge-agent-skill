---
name: virtual-recharge
description: >-
  Guide users through virtual goods proxy recharge (brand selection, SKU cascade,
  account validation, red-light confirmation, payment, fulfillment monitoring).
  Use when the user wants to recharge video/game/live-stream virtual products,
  or when working with recharge-agent-skill APIs or MCP tools.
---

# Virtual Recharge Agent Skill

## When to Use

- User wants to recharge virtual goods (腾讯视频, 抖音币, etc.)
- Integrating or testing `recharge-agent-skill` mock API or MCP tools
- Implementing buyer/seller recharge agent flows per Jiigo × 彩贝壳 PRD

## Prerequisites

1. Start mock API: `uvicorn src.app:app --host 127.0.0.1 --port 8000`
2. Optional MCP: configure `recharge_mcp/server.py` in Cursor MCP settings with `RECHARGE_API_BASE=http://127.0.0.1:8000`

## Buyer Flow (strict order)

1. `listBrands` / `list_brands`
2. `getBrandTemplate` / `get_brand_template` for selected brand
3. Collect skuLevel1 → skuLevel2; tell user `bestPrice`; `unitPrice` must match
4. Collect recharge account; validate against `inputRegex`
5. Show red-light confirmation block; wait for explicit user "确认"
6. `createRechargeOrder` / `create_recharge_order` with `X-Idempotency-Key`
7. Guide user to `payUrl`; after payment poll `getOrderStatus` every 5–10s
8. On `DELIVERED`, show `rechargeProofUrl`; remind about `autoConfirmTime`

## Seller Flow

1. `listPendingSellerOrders`
2. `sellerAcceptOrder` → `sellerStartRecharge` → `sellerDeliverOrder` (with proof URL)

## Hard Rules

- `quantity` must always be 1
- Never skip template fetch before create
- Never create order without red-light confirmation
- `unitPrice` must equal template `bestPrice`

## Reference

- Business rules: [docs/PRD_Reference.md](../../docs/PRD_Reference.md)
- Buyer prompt: [src/prompt/system_prompt.md](../../src/prompt/system_prompt.md)
- Seller prompt: [src/prompt/seller_prompt.md](../../src/prompt/seller_prompt.md)
- OpenAPI: [src/schemas/openapi.yaml](../../src/schemas/openapi.yaml)
