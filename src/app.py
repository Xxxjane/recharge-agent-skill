"""
虚拟商品代充值 Mock API 服务（FastAPI 实现）

严格遵循以下业务规则：
- 级联模板数据源（腾讯视频 / 抖音币）
- /orders/create 强制 X-Idempotency-Key 幂等校验
- quantity 必须恒等于 1 的防刷规则
- rechargeAccount 必须通过品牌模板正则校验
- 15 分钟（DEBUG 模式下 15 秒）超时未发货自动退款
- 提供模拟卖家发货接口

本文件为本地开发、Agent 集成调试、CI 验证专用 Mock 服务。
"""

import asyncio
import re
import uuid
from datetime import datetime, timedelta
from typing import Dict, Set

from fastapi import FastAPI, Header, HTTPException, Path
from pydantic import BaseModel

import json
import os
import sys
import time

# region debug instrumentation - hypothesis logging (DO NOT REMOVE until verification)
def _debug_log(hypothesis_id: str, message: str, extra: dict | None = None):
    """Append NDJSON debug line for this session. Used to diagnose 'No module named src'.
    Always writes to absolute path next to this file so the debug log is easy to find.
    """
    try:
        # Compute absolute log path based on this file's location, not cwd.
        # This guarantees the log lands at d:\虚拟代充\recharge-agent-skill\debug-d9f016.log
        if "__file__" in globals():
            _base_dir = os.path.dirname(os.path.abspath(__file__))   # .../src
            _log_path = os.path.abspath(os.path.join(_base_dir, "..", "debug-d9f016.log"))
        else:
            _log_path = os.path.abspath("debug-d9f016.log")
        entry = {
            "sessionId": "d9f016",
            "timestamp": int(time.time() * 1000),
            "location": "src/app.py",
            "message": message,
            "data": {
                "cwd": os.getcwd(),
                "sys_path_head": sys.path[:5],
                "argv": sys.argv,
                "__name__": __name__,
                "__package__": __package__,
                "has_src_dir": os.path.isdir("src"),
                "has_init_py": os.path.exists("src/__init__.py"),
                "log_path_used": _log_path,
                **(extra or {})
            },
            "hypothesisId": hypothesis_id,
            "runId": "initial"
        }
        with open(_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # never break the app for debug logs

# region evidence-based path fix for src-layout imports (addresses the "No module named 'src'" when cwd is wrong)
# When this file is loaded (whether as `python src/app.py`, `uvicorn src.app:app`, or `python -c "import src.app"`),
# we compute the project root from __file__ and ensure it is first on sys.path.
# This makes `import src` (and thus `import src.app`) succeed as long as the .py file itself was found.
import os as _os
import sys as _sys
if "__file__" in globals():
    _this_file = _os.path.abspath(__file__)
    _src_dir = _os.path.dirname(_this_file)          # .../recharge-agent-skill/src
    _project_root = _os.path.dirname(_src_dir)       # .../recharge-agent-skill
    if _project_root not in _sys.path:
        _sys.path.insert(0, _project_root)
_debug_log("H4", "path-fix block executed", {
    "project_root_added": _project_root if "__file__" in globals() else None,
    "sys_path_head_after": _sys.path[:5]
})
# endregion

# Log on every module import (this fires for `uvicorn src.app:app` and `python src/app.py`)
_debug_log("H1", "app.py module loaded - capture import context", {
    "__file__": globals().get("__file__", "no __file__ (frozen or -c)"),
    "realpath": os.path.realpath(__file__) if "__file__" in globals() else None,
    "dirname_of_file": os.path.dirname(os.path.realpath(__file__)) if "__file__" in globals() else None
})

# region debug instrumentation - early 'import src' probe (top level)
# This will execute as soon as "import src.app" or "python src/app.py" starts loading the module.
try:
    import src as _early_src
    _debug_log("H2", "Top-level probe: 'import src' SUCCEEDED when loading app.py", {
        "src_location": getattr(_early_src, "__file__", "unknown")
    })
except Exception as _early_e:
    _debug_log("H1", "Top-level probe: 'import src' FAILED when loading app.py", {
        "error_type": type(_early_e).__name__,
        "error": str(_early_e)
    })
# endregion

# =============================================================================
# 配置区
# =============================================================================

DEBUG_MODE: bool = True
"""
调试模式开关（强烈建议开发时保持 True）
- True  : 15 分钟超时自动加速为 15 秒，方便快速验证自动退款流程
- False : 严格按照 PRD 使用 15 * 60 = 900 秒
"""

TIMEOUT_SECONDS: int = 15 if DEBUG_MODE else 15 * 60
"""订单支付成功后，卖家必须在该秒数内完成发货，否则自动退款"""

# =============================================================================
# 内存数据存储（Mock 环境，无数据库）
# =============================================================================

orders: Dict[str, Dict] = {}
"""
订单主存储
key: orderId (例如 ORD_20260625_9981)
value: 订单完整信息字典，包含状态、支付信息、履约信息等
"""

idempotency_cache: Dict[str, str] = {}
"""
幂等性缓存
key: X-Idempotency-Key 请求头的值
value: 对应的 orderId
作用：相同幂等键的重复请求直接返回第一次创建的订单，防止重复扣款
"""

pending_timer_tasks: Set[asyncio.Task] = set()
"""
活跃的异步定时器任务集合
用于防止 asyncio.create_task 创建的任务被垃圾回收而提前结束
"""

# =============================================================================
# Mock 基础数据（严格对应 OpenAPI 契约中的示例）
# =============================================================================

BRANDS = [
    {
        "brandId": "brand_001",
        "brandName": "腾讯视频",
        "categoryType": "MEMBERSHIP",
        "logoUrl": "https://assets.cdn/logos/tencent_video.png"
    },
    {
        "brandId": "brand_002",
        "brandName": "抖音币",
        "categoryType": "VIRTUAL_CURRENCY",
        "logoUrl": "https://assets.cdn/logos/douyin_coin.png"
    }
]
"""
品牌列表：
- brand_001：腾讯视频（会员类）
- brand_002：抖音币（虚拟币类）
"""

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
                    {"durationOrAmount": "3个月", "bestPrice": 79.9}
                ]
            },
            {
                "level1Name": "黄金会员",
                "level2Options": [
                    {"durationOrAmount": "1个月", "bestPrice": 19.9},
                    {"durationOrAmount": "3个月", "bestPrice": 49.9}
                ]
            }
        ]
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
                    {"durationOrAmount": "300抖币", "bestPrice": 27.9}
                ]
            }
        ]
    }
}
"""
级联模板数据源：
- 腾讯视频（brand_001）：需要手机号，包含白金/黄金会员两级级联
- 抖音币（brand_002）：需要抖音UID，包含100/300抖币规格
"""

# =============================================================================
# Pydantic 请求模型
# =============================================================================

class CreateOrderRequest(BaseModel):
    """创建代充订单请求体（与 OpenAPI CreateOrderRequest 完全对齐）"""
    brandId: str
    rechargeAccount: str
    skuLevel1: str
    skuLevel2: str
    unitPrice: float
    quantity: int = 1


# =============================================================================
# 工具函数
# =============================================================================

def generate_order_id() -> str:
    """
    生成符合业务规范的订单号
    格式：ORD_YYYYMMDD_XXXX（与 PRD 示例一致）
    """
    now_str = datetime.now().strftime("%Y%m%d")
    # 使用 uuid 取后 4 位数字，保证简短且唯一
    suffix = str(uuid.uuid4().int)[:4]
    return f"ORD_{now_str}_{suffix}"


def get_brand(brand_id: str) -> Dict:
    """根据 brandId 获取品牌信息，不存在则抛 404"""
    for brand in BRANDS:
        if brand["brandId"] == brand_id:
            return brand
    raise HTTPException(status_code=404, detail=f"品牌不存在：{brand_id}")


def get_template(brand_id: str) -> Dict:
    """根据 brandId 获取级联模板，不存在则抛 404"""
    if brand_id not in TEMPLATES:
        raise HTTPException(status_code=404, detail=f"品牌模板不存在：{brand_id}")
    return TEMPLATES[brand_id]


def validate_recharge_account(template: Dict, account: str) -> bool:
    """
    使用品牌模板中定义的正则校验充值账号格式
    必须在调用 createRechargeOrder 前完成此校验
    """
    pattern = template.get("inputRegex", "")
    if not pattern:
        return False
    return bool(re.match(pattern, account or ""))


def validate_sku_selection(template: Dict, sku_level1: str, sku_level2: str) -> bool:
    """
    校验用户选择的 skuLevel1 + skuLevel2 是否存在于该品牌的级联模板中
    防止 Agent 或前端构造不存在的规格组合
    """
    for level1 in template.get("skuCascadeList", []):
        if level1.get("level1Name") == sku_level1:
            for option in level1.get("level2Options", []):
                if option.get("durationOrAmount") == sku_level2:
                    return True
    return False


async def schedule_auto_refund(order_id: str, delay_seconds: int) -> None:
    """
    【核心异步逻辑】15分钟超时未发货自动退款调度器

    流程：
    1. 等待 delay_seconds（调试模式下为 15 秒）
    2. 再次检查订单状态
    3. 若仍处于待履约状态（PENDING_MATCH / PENDING_ACCEPT / RECHARGING），则自动置为 REFUNDED
    4. 打印日志便于观察

    注意：该函数通过 asyncio.create_task 启动，需加入 pending_timer_tasks 防止被回收
    """
    print(f"[TIMER-START] 订单 {order_id} 超时退款计时器已启动，{delay_seconds} 秒后将检查是否需要自动退款（DEBUG_MODE={DEBUG_MODE}）")

    await asyncio.sleep(delay_seconds)

    order = orders.get(order_id)
    if not order:
        print(f"[TIMER-EXPIRED] 订单 {order_id} 已不存在，定时器结束")
        return

    current_status = order.get("status")

    # 只有在卖家尚未履约的状态下才执行自动退款
    if current_status in ["PENDING_MATCH", "PENDING_ACCEPT", "RECHARGING"]:
        order["status"] = "REFUNDED"
        order["statusText"] = "卖家超时未发货，系统自动全额退款"
        order["rechargeProofUrl"] = None
        print(f"[AUTO-REFUND] ✅ 订单 {order_id} 因超时未发货已自动退款，当前时间：{datetime.now()}")
    else:
        print(f"[TIMER-SKIP] 订单 {order_id} 当前状态为 {current_status}，无需自动退款")


def _register_timer_task(task: asyncio.Task) -> None:
    """将定时器任务注册到集合中，防止被垃圾回收"""
    pending_timer_tasks.add(task)
    task.add_done_callback(pending_timer_tasks.discard)


# =============================================================================
# FastAPI 应用初始化
# =============================================================================

app = FastAPI(
    title="虚拟商品代充值 Agent Skill Mock API",
    description="严格遵循 Jiigo × 彩贝壳 虚拟代充 PRD 规则的 Mock 服务，用于 AI Agent 开发与联调",
    version="1.0.0"
)


# =============================================================================
# 接口实现
# =============================================================================

@app.get("/brands", summary="获取可用充值品牌列表", tags=["Brands"])
async def list_brands():
    """
    返回当前支持的所有虚拟充值品牌。
    AI Agent 应该在用户首次表达充值意图时首先调用此接口。
    """
    return BRANDS


@app.get("/brands/{brandId}/template", summary="获取品牌的级联配置模板", tags=["Brands"])
async def get_brand_template(brandId: str = Path(..., description="品牌唯一标识")):
    """
    获取指定品牌的完整级联 SKU 模板（含账号校验正则 + 规格树 + 推荐价）。
    AI Agent 必须在下单前调用此接口，并严格按返回的级联结构引导用户选择。
    """
    template = get_template(brandId)
    return template


@app.post("/orders/create", summary="创建待支付代充订单", tags=["Orders"])
async def create_recharge_order(
    request_body: CreateOrderRequest,
    x_idempotency_key: str = Header(
        ...,
        alias="X-Idempotency-Key",
        description="幂等性键（必填）。相同 Key 的重复请求将返回首次创建的订单，防止重复扣款。"
    )
):
    """
    创建代充订单（占位符订单）。

    强制业务规则（违反即返回 400）：
    1. 必须携带 X-Idempotency-Key 请求头
    2. quantity 必须恒等于 1
    3. rechargeAccount 必须符合对应品牌模板的 inputRegex
    4. skuLevel1 + skuLevel2 必须存在于该品牌的级联模板中

    幂等性处理：
    - 同一个 X-Idempotency-Key 第一次请求会创建订单并缓存
    - 后续相同 Key 请求直接返回第一次创建的订单数据（不重复创建、不重复扣款）
    """
    # -------------------------- 1. 幂等键校验 --------------------------
    if not x_idempotency_key or not x_idempotency_key.strip():
        raise HTTPException(
            status_code=400,
            detail="请求头缺少 X-Idempotency-Key，幂等性校验失败"
        )

    # 如果该幂等键已使用过，直接返回已创建的订单（核心防重复逻辑）
    if x_idempotency_key in idempotency_cache:
        existing_order_id = idempotency_cache[x_idempotency_key]
        existing_order = orders.get(existing_order_id)
        if existing_order:
            print(f"[IDEMPOTENCY-HIT] 幂等键 {x_idempotency_key} 命中，已返回订单 {existing_order_id}")
            return {
                "orderId": existing_order["orderId"],
                "payUrl": existing_order["payUrl"],
                "timeoutSeconds": existing_order["timeoutSeconds"]
            }

    # -------------------------- 2. 数量防刷校验 --------------------------
    if request_body.quantity != 1:
        raise HTTPException(
            status_code=400,
            detail="代充安全机制限制，单次交易仅支持购买 1 份"
        )

    # -------------------------- 3. 品牌与模板获取 --------------------------
    template = get_template(request_body.brandId)

    # -------------------------- 4. 账号格式校验（红灯泡前置） --------------------------
    if not validate_recharge_account(template, request_body.rechargeAccount):
        raise HTTPException(
            status_code=400,
            detail="充值账号格式不正确，请根据模板中的规则重新输入"
        )

    # -------------------------- 5. SKU 级联规格校验 --------------------------
    if not validate_sku_selection(template, request_body.skuLevel1, request_body.skuLevel2):
        raise HTTPException(
            status_code=400,
            detail="所选规格（skuLevel1 + skuLevel2）与品牌模板不匹配，请重新选择"
        )

    # -------------------------- 6. 创建订单 --------------------------
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
        "timeoutSeconds": TIMEOUT_SECONDS,
        "rechargeProofUrl": None,
        "autoConfirmTime": None,
        "idempotencyKey": x_idempotency_key
    }

    # 落库
    orders[order_id] = order
    idempotency_cache[x_idempotency_key] = order_id

    print(f"[ORDER-CREATED] 订单 {order_id} 创建成功，状态：PENDING_PAY，幂等键：{x_idempotency_key}")

    # -------------------------- 7. 返回创建响应 --------------------------
    return {
        "orderId": order_id,
        "payUrl": order["payUrl"],
        "timeoutSeconds": order["timeoutSeconds"]
    }


@app.get("/orders/{orderId}/status", summary="轮询/获取订单实时状态", tags=["Orders"])
async def get_order_status(orderId: str = Path(..., description="订单唯一标识")):
    """
    查询订单最新状态。
    AI Agent 支付成功后应轮询此接口，当 status 变为 DELIVERED 时必须展示 rechargeProofUrl。
    """
    if orderId not in orders:
        raise HTTPException(status_code=404, detail="订单不存在")

    order = orders[orderId]
    return {
        "orderId": order["orderId"],
        "status": order["status"],
        "statusText": order["statusText"],
        "rechargeProofUrl": order.get("rechargeProofUrl"),
        "autoConfirmTime": order.get("autoConfirmTime")
    }


# =============================================================================
# Mock 调试辅助接口（仅用于本地 / 集成测试，生产环境请移除）
# =============================================================================

@app.post("/orders/{orderId}/mock-pay-success", summary="【调试】模拟买家支付成功", tags=["Mock"])
async def mock_pay_success(orderId: str = Path(..., description="订单ID")):
    """
    模拟用户完成支付。
    支付成功后：
    - 订单状态流转为 PENDING_MATCH
    - 启动 15 分钟（或 15 秒）超时退款计时器
    """
    if orderId not in orders:
        raise HTTPException(status_code=404, detail="订单不存在")

    order = orders[orderId]

    if order["status"] != "PENDING_PAY":
        raise HTTPException(
            status_code=400,
            detail=f"当前状态 {order['status']} 无法执行支付操作"
        )

    # 流转到待匹配卖家状态
    order["status"] = "PENDING_MATCH"
    order["statusText"] = "等待卖家接单"

    # 启动异步超时退款定时器（核心业务逻辑）
    delay = 15 if DEBUG_MODE else 15 * 60
    timer_task = asyncio.create_task(schedule_auto_refund(orderId, delay))
    _register_timer_task(timer_task)

    print(f"[MOCK-PAY] 订单 {orderId} 模拟支付成功，已启动超时计时器（{delay}秒）")

    return {
        "message": "模拟支付成功，订单已进入履约流程",
        "orderId": orderId,
        "status": order["status"],
        "timeoutSeconds": order["timeoutSeconds"]
    }


@app.post("/orders/{orderId}/mock-deliver", summary="【调试】模拟卖家发货", tags=["Mock"])
async def mock_deliver_order(orderId: str = Path(..., description="订单ID")):
    """
    模拟卖家完成接单 + 充值 + 上传凭证。
    调用后：
    - 状态变为 DELIVERED
    - 自动附加 Mock 充值成功截图（rechargeProofUrl）
    - 计算自动确认收货时间（发货次日 23:59:59）
    """
    if orderId not in orders:
        raise HTTPException(status_code=404, detail="订单不存在")

    order = orders[orderId]

    # 允许从任意待履约状态直接发货，便于测试
    if order["status"] not in ["PENDING_MATCH", "PENDING_ACCEPT", "RECHARGING", "PENDING_PAY"]:
        raise HTTPException(
            status_code=400,
            detail=f"当前状态 {order['status']} 无法执行发货操作"
        )

    # 执行发货
    order["status"] = "DELIVERED"
    order["statusText"] = "卖家已发货"
    order["rechargeProofUrl"] = "https://assets.cdn/proofs/proof_demo.jpg"

    # 计算自动确认收货时间（PRD 定义：发货次日 23:59:59）
    now = datetime.now()
    auto_confirm_dt = (now + timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=0)
    order["autoConfirmTime"] = auto_confirm_dt.strftime("%Y-%m-%d %H:%M:%S")

    print(f"[MOCK-DELIVER] 订单 {orderId} 模拟发货成功，凭证已上传，自动确认时间：{order['autoConfirmTime']}")

    return {
        "message": "模拟发货成功",
        "orderId": orderId,
        "status": order["status"],
        "rechargeProofUrl": order["rechargeProofUrl"],
        "autoConfirmTime": order["autoConfirmTime"]
    }


# =============================================================================
# 调试辅助接口
# =============================================================================

@app.get("/debug/orders", summary="【调试】列出所有订单", tags=["Debug"])
async def debug_list_all_orders():
    """方便开发者快速查看当前内存中的所有订单状态"""
    return {
        "total": len(orders),
        "debugMode": DEBUG_MODE,
        "timeoutSeconds": TIMEOUT_SECONDS,
        "orders": list(orders.values())
    }


@app.get("/debug/clear", summary="【调试】清空所有内存数据", tags=["Debug"])
async def debug_clear_all():
    """测试时快速重置环境"""
    global orders, idempotency_cache, pending_timer_tasks
    orders.clear()
    idempotency_cache.clear()
    pending_timer_tasks.clear()
    return {"message": "所有内存数据已清空"}


# =============================================================================
# 启动入口
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    # region debug instrumentation - __main__ invocation
    _debug_log("H1", "__main__ entered - direct script or -m invocation", {
        "invocation": "if __name__ == '__main__'"
    })
    # Try to reproduce the exact 'import src' that the user experienced
    try:
        import src as _src_pkg
        _debug_log("H2", "SUCCESS: 'import src' worked inside __main__", {
            "src_file": getattr(_src_pkg, "__file__", None)
        })
    except Exception as _e:
        _debug_log("H1", "FAILED: 'import src' raised inside __main__", {
            "error_type": type(_e).__name__,
            "error": str(_e)
        })
    # endregion
    print("=" * 60)
    print("虚拟商品代充值 Mock API 服务启动中...")
    print(f"DEBUG_MODE = {DEBUG_MODE} (15分钟超时已加速为 {TIMEOUT_SECONDS} 秒)")
    print("推荐使用以下命令启动：")
    print("  uvicorn src.app:app --reload --port 8000")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
