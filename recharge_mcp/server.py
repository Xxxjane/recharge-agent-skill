"""
MCP Server for Virtual Recharge Agent Skill.

Run from project root:
  python -m recharge_mcp.server
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

API_BASE = os.getenv("RECHARGE_API_BASE", "http://127.0.0.1:8000").rstrip("/")
server = FastMCP("virtual-recharge-skill")


async def _request(method: str, path: str, **kwargs) -> Any:
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.request(method, path, **kwargs)
        resp.raise_for_status()
        if resp.content:
            return resp.json()
        return {}


@server.tool()
async def list_brands() -> str:
    """Get supported virtual recharge brands. Call first when user wants to recharge."""
    data = await _request("GET", "/brands")
    return json.dumps(data, ensure_ascii=False)


@server.tool()
async def get_brand_template(brand_id: str) -> str:
    """Get cascade SKU template, inputRegex and bestPrice for a brand."""
    data = await _request("GET", f"/brands/{brand_id}/template")
    return json.dumps(data, ensure_ascii=False)


@server.tool()
async def create_recharge_order(
    brand_id: str,
    recharge_account: str,
    sku_level1: str,
    sku_level2: str,
    unit_price: float,
    idempotency_key: str | None = None,
) -> str:
    """Create order after user confirmed red-light dialog. quantity is always 1."""
    key = idempotency_key or str(uuid.uuid4())
    payload = {
        "brandId": brand_id,
        "rechargeAccount": recharge_account,
        "skuLevel1": sku_level1,
        "skuLevel2": sku_level2,
        "unitPrice": unit_price,
        "quantity": 1,
    }
    data = await _request(
        "POST",
        "/orders/create",
        json=payload,
        headers={"X-Idempotency-Key": key},
    )
    return json.dumps(data, ensure_ascii=False)


@server.tool()
async def get_order_status(order_id: str) -> str:
    """Poll order status after payment. Show rechargeProofUrl when DELIVERED."""
    data = await _request("GET", f"/orders/{order_id}/status")
    return json.dumps(data, ensure_ascii=False)


@server.tool()
async def confirm_receipt(order_id: str) -> str:
    """Buyer confirms receipt when status is DELIVERED."""
    data = await _request("POST", f"/orders/{order_id}/confirm-receipt")
    return json.dumps(data, ensure_ascii=False)


@server.tool()
async def list_pending_seller_orders() -> str:
    """Seller: list orders pending acceptance or fulfillment."""
    data = await _request("GET", "/seller/orders/pending")
    return json.dumps(data, ensure_ascii=False)


@server.tool()
async def seller_accept_order(order_id: str) -> str:
    """Seller accepts order: PENDING_MATCH -> PENDING_ACCEPT."""
    data = await _request("POST", f"/seller/orders/{order_id}/accept")
    return json.dumps(data, ensure_ascii=False)


@server.tool()
async def seller_start_recharge(order_id: str) -> str:
    """Seller starts recharge: PENDING_ACCEPT -> RECHARGING."""
    data = await _request("POST", f"/seller/orders/{order_id}/start-recharge")
    return json.dumps(data, ensure_ascii=False)


@server.tool()
async def seller_deliver_order(
    order_id: str,
    recharge_proof_url: str = "https://assets.cdn/proofs/proof_demo.jpg",
) -> str:
    """Seller uploads proof and delivers: RECHARGING -> DELIVERED."""
    data = await _request(
        "POST",
        f"/seller/orders/{order_id}/deliver",
        json={"rechargeProofUrl": recharge_proof_url},
    )
    return json.dumps(data, ensure_ascii=False)


def main() -> None:
    server.run()


if __name__ == "__main__":
    main()
