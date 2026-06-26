# MCP Integration

Expose recharge tools to any MCP-compatible agent (Cursor, Claude Desktop, etc.).

## Cursor / Claude Desktop config

Add to MCP settings (`.cursor/mcp.json` or Claude config):

```json
{
  "mcpServers": {
    "virtual-recharge": {
      "command": "python",
      "args": ["-m", "recharge_mcp.server"],
      "cwd": "/path/to/recharge-agent-skill",
      "env": {
        "RECHARGE_API_BASE": "http://127.0.0.1:8000"
      }
    }
  }
}
```

## Prerequisites

1. `pip install -r requirements.txt`
2. Start API: `uvicorn src.app:app --host 127.0.0.1 --port 8000`
3. Run MCP: `python -m recharge_mcp.server`

## Tools exposed


| MCP Tool                   | REST equivalent                         |
| -------------------------- | --------------------------------------- |
| list_brands                | GET /brands                             |
| get_brand_template         | GET /brands/{id}/template               |
| create_recharge_order      | POST /orders/create                     |
| get_order_status           | GET /orders/{id}/status                 |
| confirm_receipt            | POST /orders/{id}/confirm-receipt       |
| list_pending_seller_orders | GET /seller/orders/pending              |
| seller_accept_order        | POST /seller/orders/{id}/accept         |
| seller_start_recharge      | POST /seller/orders/{id}/start-recharge |
| seller_deliver_order       | POST /seller/orders/{id}/deliver        |


See also [.cursor/skills/virtual-recharge/SKILL.md](../.cursor/skills/virtual-recharge/SKILL.md).