# Cursor MCP 配置示例

1. 启动 API：`uvicorn src.app:app --port 8000`
2. 在 Cursor MCP 设置中添加：

```json
{
  "mcpServers": {
    "virtual-recharge": {
      "command": "python",
      "args": ["-m", "recharge_mcp.server"],
      "cwd": "D:/path/to/recharge-agent-skill",
      "env": {
        "RECHARGE_API_BASE": "http://127.0.0.1:8000"
      }
    }
  }
}
```

3. 在 Agent 对话中说：「帮我充腾讯视频白金会员 3 个月」
4. Agent 应通过 MCP 调用 `list_brands` → `get_brand_template` → …
