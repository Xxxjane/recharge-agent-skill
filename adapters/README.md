# Channel Adapters

渠道 Adapter 层将外部 IM/支付平台与 Skill 核心 API 解耦。当前为 **接口 stub**，供后续接入微信、支付宝、美团等。

## 目录

```
adapters/
├── base.py          # 抽象 Adapter 接口
├── wechat/          # 微信小程序 / 客服消息
├── alipay/          # 支付宝收银台与回调
└── meituan/         # 美团（预留）
```

## 接入原则

1. Adapter 只负责：消息格式转换、OAuth/签名、支付回调 → 调用核心 `POST /orders/create` 等 REST API
2. 业务规则（红灯泡、quantity=1、价格校验）仍在核心 API + Prompt 层
3. 每个 Adapter 实现 `ChannelAdapter` 基类

## 状态

| 渠道 | 状态 | 说明 |
|------|------|------|
| WeChat | stub | 消息入站/出站、支付回调占位 |
| Alipay | stub | payUrl 替换与 notify_url 占位 |
| Meituan | stub | 预留，待 PRD 明确场景 |

详见各子目录 README。
