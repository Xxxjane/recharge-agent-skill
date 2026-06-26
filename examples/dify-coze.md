# Dify 集成示例

1. 启动 Mock API 并获取可访问 URL（本地可用 ngrok 暴露 8000）
2. Dify → 工具 → 导入自定义工具 → 上传 [integration/dify/tool_config.json](../integration/dify/tool_config.json)
3. 将 `base_url` 改为你的 API 地址
4. 在应用 System Prompt 中粘贴 [src/prompt/system_prompt.md](../src/prompt/system_prompt.md)
5. 测试话术：「我想充腾讯视频白金会员 3 个月，手机号 13800138000」

卖家侧 Agent 使用 [src/prompt/seller_prompt.md](../src/prompt/seller_prompt.md) 并配置卖家相关工具。