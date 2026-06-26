"""Meituan channel adapter (stub, reserved)."""

from __future__ import annotations

from typing import Any, Dict

from adapters.base import ChannelAdapter


class MeituanAdapter(ChannelAdapter):
    channel_name = "meituan"

    async def send_message(self, user_id: str, content: str, **kwargs: Any) -> None:
        raise NotImplementedError("Meituan adapter reserved until PRD defines integration scenario")

    async def parse_inbound(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"user_id": payload.get("user_id", ""), "text": payload.get("message", ""), "metadata": payload}

    async def create_payment(self, order_id: str, amount: float, **kwargs: Any) -> str:
        return f"https://pay.meituan.com/mock?orderId={order_id}&amount={amount}"

    async def handle_payment_callback(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"order_id": payload.get("order_id", ""), "paid": payload.get("status") == "paid"}
