"""
虚拟商品代充值 Mock API 服务（FastAPI 实现）

买家侧 + 卖家侧完整状态机，严格遵循 PRD 业务规则。
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, Set

from fastapi import FastAPI, Header, HTTPException, Path
from pydantic import BaseModel, Field

from src.config import (
    AUTO_CONFIRM_DELAY_SECONDS,
    AUTO_CONFIRM_USE_SHORT_DELAY,
    DEBUG_MODE,
    FULFILLMENT_TIMEOUT_SECONDS,
    PAY_TIMEOUT_SECONDS,
)

# Ensure project root is on sys.path for `uvicorn src.app:app`
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# =============================================================================
# In-memory storage
# =============================================================================

orders: Dict[str, Dict] = {}
idempotency_cache: Dict[str, str] = {}
pending_timer_tasks: Set[asyncio.Task] = set()

# =============================================================================
# Mock catalog
# =============================================================================

BRANDS = [
    {
        "brandId": "brand_001",
        "brandName": "腾讯视频",
        "categoryType": "MEMBERSHIP",
        "logoUrl": "https://assets.cdn/logos/tencent_video.png",
    },
    {
        "brandId": "brand_002",
        "brandName": "抖音币",
        "categoryType": "VIRTUAL_CURRENCY",
        "logoUrl": "https://assets.cdn/logos/douyin_coin.png",
    },
]

TEMPLATES: Dict[str, Dict] = {
    "brand_001": {
        "brandId": "brand_001",
        "inputFieldName": "充值账号(手机号)",
        "inputRegex": r"^1[3-9]\d{9}$",
        "skuCascadeList": [
            {
                "level1Name": "白金会员",
                "level2Options": [
                    {"durationOrAmount": "1个月", "bestPrice": 29.9},
                    {"durationOrAmount": "3个月", "bestPrice": 79.9},
                ],
            },
            {
                "level1Name": "黄金会员",
                "level2Options": [
                    {"durationOrAmount": "1个月", "bestPrice": 19.9},
                    {"durationOrAmount": "3个月", "bestPrice": 49.9},
                ],
            },
        ],
    },
    "brand_002": {
        "brandId": "brand_002",
        "inputFieldName": "抖音 UID",
        "inputRegex": r"^\d{5,20}$",
        "skuCascadeList": [
            {
                "level1Name": "抖音币",
                "level2Options": [
                    {"durationOrAmount": "100抖币", "bestPrice": 9.9},
                    {"durationOrAmount": "300抖币", "bestPrice": 27.9},
                ],
            }
        ],
    },
}

FULFILLMENT_STATUSES = {"PENDING_MATCH", "PENDING_ACCEPT", "RECHARGING"}


# =============================================================================
# Request models
# =============================================================================


class CreateOrderRequest(BaseModel):
    brandId: str
    rechargeAccount: str
    skuLevel1: str
    skuLevel2: str
    unitPrice: float
    quantity: int = 1


class DeliverOrderRequest(BaseModel):
    rechargeProofUrl: str = Field(
        default="https://assets.cdn/proofs/proof_demo.jpg",
        description="卖家上传的充值凭证截图 URL",
    )


# =============================================================================
# Helpers
# =============================================================================


def generate_order_id() -> str:
    now_str = datetime.now().strftime("%Y%m%d")
    suffix = str(uuid.uuid4().int)[:4]
    return f"ORD_{now_str}_{suffix}"


def get_template(brand_id: str) -> Dict:
    if brand_id not in TEMPLATES:
        raise HTTPException(status_code=404, detail=f"品牌模板不存在：{brand_id}")
    return TEMPLATES[brand_id]


def validate_recharge_account(template: Dict, account: str) -> bool:
    pattern = template.get("inputRegex", "")
    if not pattern:
        return False
    return bool(re.match(pattern, account or ""))


def validate_sku_selection(template: Dict, sku_level1: str, sku_level2: str) -> bool:
    return get_best_price(template, sku_level1, sku_level2) is not None


def get_best_price(template: Dict, sku_level1: str, sku_level2: str) -> Optional[float]:
    for level1 in template.get("skuCascadeList", []):
        if level1.get("level1Name") == sku_level1:
            for option in level1.get("level2Options", []):
                if option.get("durationOrAmount") == sku_level2:
                    return float(option["bestPrice"])
    return None


def _register_timer_task(task: asyncio.Task) -> None:
    pending_timer_tasks.add(task)
    task.add_done_callback(pending_timer_tasks.discard)


def compute_auto_confirm_time(from_dt: Optional[datetime] = None) -> str:
    base = from_dt or datetime.now()
    if AUTO_CONFIRM_USE_SHORT_DELAY:
        target = base + timedelta(seconds=AUTO_CONFIRM_DELAY_SECONDS)
    else:
        target = (base + timedelta(days=1)).replace(
            hour=23, minute=59, second=59, microsecond=0
        )
    return target.strftime("%Y-%m-%d %H:%M:%S")


def _auto_confirm_delay_seconds(auto_confirm_time: str) -> float:
    if AUTO_CONFIRM_USE_SHORT_DELAY:
        return AUTO_CONFIRM_DELAY_SECONDS
    target = datetime.strptime(auto_confirm_time, "%Y-%m-%d %H:%M:%S")
    return max(0.0, (target - datetime.now()).total_seconds())


def order_status_response(order: Dict) -> Dict:
    return {
        "orderId": order["orderId"],
        "status": order["status"],
        "statusText": order["statusText"],
        "rechargeProofUrl": order.get("rechargeProofUrl"),
        "autoConfirmTime": order.get("autoConfirmTime"),
    }


def order_created_response(order: Dict) -> Dict:
    return {
        "orderId": order["orderId"],
        "payUrl": order["payUrl"],
        "payTimeoutSeconds": order["payTimeoutSeconds"],
        "fulfillmentTimeoutSeconds": order["fulfillmentTimeoutSeconds"],
    }


async def schedule_payment_timeout(order_id: str, delay_seconds: int) -> None:
    await asyncio.sleep(delay_seconds)
    order = orders.get(order_id)
    if not order:
        return
    if order.get("status") == "PENDING_PAY":
        order["status"] = "CLOSED"
        order["statusText"] = "支付超时，订单已关闭"


async def schedule_auto_refund(order_id: str, delay_seconds: int) -> None:
    await asyncio.sleep(delay_seconds)
    order = orders.get(order_id)
    if not order:
        return
    if order.get("status") in FULFILLMENT_STATUSES:
        order["status"] = "REFUNDED"
        order["statusText"] = "卖家超时未发货，系统自动全额退款"
        order["rechargeProofUrl"] = None


async def schedule_auto_confirm(order_id: str, delay_seconds: float) -> None:
    await asyncio.sleep(delay_seconds)
    order = orders.get(order_id)
    if not order:
        return
    if order.get("status") == "DELIVERED":
        order["status"] = "COMPLETED"
        order["statusText"] = "已自动确认收货，交易完成"


def start_fulfillment_timer(order_id: str) -> None:
    task = asyncio.create_task(
        schedule_auto_refund(order_id, FULFILLMENT_TIMEOUT_SECONDS)
    )
    _register_timer_task(task)


def start_auto_confirm_timer(order_id: str, auto_confirm_time: str) -> None:
    delay = _auto_confirm_delay_seconds(auto_confirm_time)
    task = asyncio.create_task(schedule_auto_confirm(order_id, delay))
    _register_timer_task(task)


def get_order_or_404(order_id: str) -> Dict:
    if order_id not in orders:
        raise HTTPException(status_code=404, detail="订单不存在")
    return orders[order_id]


def require_status(order: Dict, allowed: set[str], action: str) -> None:
    if order["status"] not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"当前状态 {order['status']} 无法执行{action}",
        )


# =============================================================================
# FastAPI app
# =============================================================================

app = FastAPI(
    title="虚拟商品代充值 Agent Skill Mock API",
    description="Jiigo × 彩贝壳 虚拟代充 PRD Mock 服务（买家侧 + 卖家侧）",
    version="1.1.0",
)


# --- Buyer: catalog ---


@app.get("/brands", tags=["Brands"])
async def list_brands():
    return BRANDS


@app.get("/brands/{brandId}/template", tags=["Brands"])
async def get_brand_template(brandId: str = Path(...)):
    return get_template(brandId)


# --- Buyer: orders ---


@app.post("/orders/create", tags=["Orders"])
async def create_recharge_order(
    request_body: CreateOrderRequest,
    x_idempotency_key: str = Header(..., alias="X-Idempotency-Key"),
):
    if not x_idempotency_key or not x_idempotency_key.strip():
        raise HTTPException(status_code=400, detail="请求头缺少 X-Idempotency-Key")

    if x_idempotency_key in idempotency_cache:
        existing = orders.get(idempotency_cache[x_idempotency_key])
        if existing:
            return order_created_response(existing)

    if request_body.quantity != 1:
        raise HTTPException(status_code=400, detail="代充安全机制限制，单次交易仅支持购买 1 份")

    template = get_template(request_body.brandId)

    if not validate_recharge_account(template, request_body.rechargeAccount):
        raise HTTPException(status_code=400, detail="充值账号格式不正确，请根据模板中的规则重新输入")

    if not validate_sku_selection(template, request_body.skuLevel1, request_body.skuLevel2):
        raise HTTPException(status_code=400, detail="所选规格与品牌模板不匹配，请重新选择")

    best_price = get_best_price(template, request_body.skuLevel1, request_body.skuLevel2)
    if best_price is None or abs(request_body.unitPrice - best_price) > 0.001:
        raise HTTPException(
            status_code=400,
            detail=f"单价必须与模板 bestPrice 一致（期望 {best_price}，实际 {request_body.unitPrice}）",
        )

    order_id = generate_order_id()
    order = {
        "orderId": order_id,
        "brandId": request_body.brandId,
        "rechargeAccount": request_body.rechargeAccount,
        "skuLevel1": request_body.skuLevel1,
        "skuLevel2": request_body.skuLevel2,
        "unitPrice": request_body.unitPrice,
        "quantity": 1,
        "status": "PENDING_PAY",
        "statusText": "等待支付",
        "createdAt": datetime.now().isoformat(),
        "payUrl": f"https://pay.platform.open/cashier?orderId={order_id}",
        "payTimeoutSeconds": PAY_TIMEOUT_SECONDS,
        "fulfillmentTimeoutSeconds": FULFILLMENT_TIMEOUT_SECONDS,
        "rechargeProofUrl": None,
        "autoConfirmTime": None,
        "idempotencyKey": x_idempotency_key,
    }
    orders[order_id] = order
    idempotency_cache[x_idempotency_key] = order_id

    pay_timer = asyncio.create_task(schedule_payment_timeout(order_id, PAY_TIMEOUT_SECONDS))
    _register_timer_task(pay_timer)

    return order_created_response(order)


@app.get("/orders/{orderId}/status", tags=["Orders"])
async def get_order_status(orderId: str = Path(...)):
    return order_status_response(get_order_or_404(orderId))


@app.post("/orders/{orderId}/confirm-receipt", tags=["Orders"])
async def confirm_receipt(orderId: str = Path(...)):
    order = get_order_or_404(orderId)
    require_status(order, {"DELIVERED"}, "确认收货")
    order["status"] = "COMPLETED"
    order["statusText"] = "买家已确认收货，交易完成"
    return order_status_response(order)


# --- Seller ---


@app.get("/seller/orders/pending", tags=["Seller"])
async def list_pending_seller_orders():
    pending = [
        o
        for o in orders.values()
        if o["status"] in FULFILLMENT_STATUSES | {"PENDING_MATCH"}
    ]
    return {"total": len(pending), "orders": pending}


@app.post("/seller/orders/{orderId}/accept", tags=["Seller"])
async def seller_accept_order(orderId: str = Path(...)):
    order = get_order_or_404(orderId)
    require_status(order, {"PENDING_MATCH"}, "接单")
    order["status"] = "PENDING_ACCEPT"
    order["statusText"] = "卖家已接单，等待充值"
    return order_status_response(order)


@app.post("/seller/orders/{orderId}/start-recharge", tags=["Seller"])
async def seller_start_recharge(orderId: str = Path(...)):
    order = get_order_or_404(orderId)
    require_status(order, {"PENDING_ACCEPT"}, "开始充值")
    order["status"] = "RECHARGING"
    order["statusText"] = "充值进行中"
    return order_status_response(order)


@app.post("/seller/orders/{orderId}/deliver", tags=["Seller"])
async def seller_deliver_order(
    orderId: str = Path(...),
    body: DeliverOrderRequest = DeliverOrderRequest(),
):
    order = get_order_or_404(orderId)
    require_status(order, {"RECHARGING"}, "发货")
    order["status"] = "DELIVERED"
    order["statusText"] = "卖家已发货"
    order["rechargeProofUrl"] = body.rechargeProofUrl
    order["autoConfirmTime"] = compute_auto_confirm_time()
    start_auto_confirm_timer(orderId, order["autoConfirmTime"])
    return order_status_response(order)


# --- Mock / debug ---


@app.post("/orders/{orderId}/mock-pay-success", tags=["Mock"])
async def mock_pay_success(orderId: str = Path(...)):
    order = get_order_or_404(orderId)
    require_status(order, {"PENDING_PAY"}, "支付")
    order["status"] = "PENDING_MATCH"
    order["statusText"] = "等待卖家接单"
    start_fulfillment_timer(orderId)
    return {
        "message": "模拟支付成功，订单已进入履约流程",
        "orderId": orderId,
        "status": order["status"],
        "fulfillmentTimeoutSeconds": order["fulfillmentTimeoutSeconds"],
    }


@app.post("/orders/{orderId}/mock-deliver", tags=["Mock"])
async def mock_deliver_order(orderId: str = Path(...)):
    """Shortcut: accept + start-recharge + deliver in one call for tests."""
    order = get_order_or_404(orderId)
    if order["status"] == "PENDING_MATCH":
        order["status"] = "PENDING_ACCEPT"
    if order["status"] == "PENDING_ACCEPT":
        order["status"] = "RECHARGING"
    require_status(order, {"RECHARGING"}, "发货")
    order["status"] = "DELIVERED"
    order["statusText"] = "卖家已发货"
    order["rechargeProofUrl"] = "https://assets.cdn/proofs/proof_demo.jpg"
    order["autoConfirmTime"] = compute_auto_confirm_time()
    start_auto_confirm_timer(orderId, order["autoConfirmTime"])
    return order_status_response(order)


@app.get("/debug/orders", tags=["Debug"])
async def debug_list_all_orders():
    return {
        "total": len(orders),
        "debugMode": DEBUG_MODE,
        "payTimeoutSeconds": PAY_TIMEOUT_SECONDS,
        "fulfillmentTimeoutSeconds": FULFILLMENT_TIMEOUT_SECONDS,
        "orders": list(orders.values()),
    }


@app.get("/debug/clear", tags=["Debug"])
async def debug_clear_all():
    global orders, idempotency_cache, pending_timer_tasks
    orders.clear()
    idempotency_cache.clear()
    pending_timer_tasks.clear()
    return {"message": "所有内存数据已清空"}


if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("虚拟商品代充值 Mock API 启动")
    print(f"DEBUG_MODE={DEBUG_MODE}")
    print(f"payTimeout={PAY_TIMEOUT_SECONDS}s  fulfillmentTimeout={FULFILLMENT_TIMEOUT_SECONDS}s")
    print("  uvicorn src.app:app --reload --port 8000")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
