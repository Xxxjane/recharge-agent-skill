"""Alipay cashier adapter (stub)."""

from __future__ import annotations

from typing import Any, Dict

from adapters.base import ChannelAdapter


class AlipayAdapter(ChannelAdapter):
    channel_name = "alipay"

    def __init__(self, app_id: str = ""):
        self.app_id = app_id

    async def send_message(self, user_id: str, content: str, **kwargs: Any) -> None:
        raise NotImplementedError("Alipay has no IM channel in this skill; use app push separately")

    async def parse_inbound(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"user_id": payload.get("buyer_id", ""), "text": "", "metadata": payload}

    async def create_payment(self, order_id: str, amount: float, **kwargs: Any) -> str:
        return f"https://openapi.alipay.com/gateway.do?out_trade_no={order_id}&total_amount={amount}"

    async def handle_payment_callback(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "order_id": payload.get("out_trade_no", ""),
            "paid": payload.get("trade_status") == "TRADE_SUCCESS",
        }
