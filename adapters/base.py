"""Base channel adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class ChannelAdapter(ABC):
    """Bridge external channel (WeChat, Alipay, Meituan) to recharge core API."""

    channel_name: str = "base"

    @abstractmethod
    async def send_message(self, user_id: str, content: str, **kwargs: Any) -> None:
        """Send outbound message to user on this channel."""

    @abstractmethod
    async def parse_inbound(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize inbound webhook/event to {user_id, text, metadata}."""

    @abstractmethod
    async def create_payment(self, order_id: str, amount: float, **kwargs: Any) -> str:
        """Return payment URL or deep link for the channel."""

    @abstractmethod
    async def handle_payment_callback(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Verify signature and return {order_id, paid: bool}."""
