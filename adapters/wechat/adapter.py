"""WeChat Mini Program / customer service adapter (stub)."""

from __future__ import annotations

from typing import Any, Dict

from adapters.base import ChannelAdapter


class WeChatAdapter(ChannelAdapter):
    channel_name = "wechat"

    def __init__(self, app_id: str = "", app_secret: str = ""):
        self.app_id = app_id
        self.app_secret = app_secret

    async def send_message(self, user_id: str, content: str, **kwargs: Any) -> None:
        raise NotImplementedError("WeChat send_message: configure app_id and WeChat API SDK")

    async def parse_inbound(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "user_id": payload.get("FromUserName", ""),
            "text": payload.get("Content", ""),
            "metadata": payload,
        }

    async def create_payment(self, order_id: str, amount: float, **kwargs: Any) -> str:
        return f"weixin://wxpay/bizpayurl?orderId={order_id}&amount={amount}"

    async def handle_payment_callback(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"order_id": payload.get("out_trade_no", ""), "paid": payload.get("result_code") == "SUCCESS"}
