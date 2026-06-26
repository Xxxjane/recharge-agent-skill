# WeChat Adapter (Stub)

接入点：
- 小程序客服消息 / 订阅消息 → 转发给 Agent
- 微信支付 JSAPI → 替换 mock `payUrl`
- 支付结果 notify → 调用核心 API `mock-pay-success` 或生产支付确认接口

环境变量（未来）：`WECHAT_APP_ID`, `WECHAT_APP_SECRET`, `WECHAT_MCH_ID`
