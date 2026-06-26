# Alipay Adapter (Stub)

接入点：
- 手机网站支付 / 当面付 → 生成真实 `payUrl`
- 异步通知 `notify_url` → 验签后更新订单为已支付

环境变量（未来）：`ALIPAY_APP_ID`, `ALIPAY_PRIVATE_KEY`, `ALIPAY_PUBLIC_KEY`
