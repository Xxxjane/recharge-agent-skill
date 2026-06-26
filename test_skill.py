"""
虚拟商品代充值 Skill 自动化测试脚本

使用方法（确保 Mock 服务已启动）：
    1. 启动服务（推荐）：
       cd src
       python app.py
       # 或 uvicorn app:app --reload --port 8000

    2. 在另一个终端运行测试：
       python test_skill.py

依赖：
    pip install requests

本脚本覆盖完整的业务闭环测试，包括异常拦截、正常下单、幂等性、15秒自动退款（DEBUG_MODE）。
"""

import sys
import time
import uuid

import requests

# =============================================================================
# 配置
# =============================================================================
BASE_URL = "http://localhost:8000"
TIMEOUT = 10  # 单次请求超时
POLL_INTERVAL = 2  # Case 5 轮询间隔（秒）
MAX_WAIT_FOR_REFUND = 25  # Case 5 最大等待时间（秒）

# 选择的测试品牌（腾讯视频）
TEST_BRAND_ID = "brand_001"
VALID_ACCOUNT = "13800138000"  # 符合 ^1[3-9]\d{9}$ 的手机号
INVALID_ACCOUNT = "12345678901"  # 不符合正则（第二位是2）

session = requests.Session()
session.headers.update({"User-Agent": "recharge-skill-test/1.0"})


# =============================================================================
# 辅助函数
# =============================================================================
def check_server_alive() -> None:
    """检查 Mock 服务是否可用"""
    try:
        resp = session.get(f"{BASE_URL}/brands", timeout=5)
        if resp.status_code != 200:
            raise RuntimeError(f"服务返回异常状态码: {resp.status_code}")
    except Exception as e:
        print(f"❌ 无法连接到 Mock 服务 {BASE_URL}")
        print("   请先启动服务：")
        print("     cd src")
        print("     python app.py")
        print(f"错误信息: {e}")
        sys.exit(1)


def get_brands():
    resp = session.get(f"{BASE_URL}/brands", timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def get_template(brand_id: str):
    resp = session.get(f"{BASE_URL}/brands/{brand_id}/template", timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def create_order(
    brand_id: str,
    recharge_account: str,
    sku_level1: str,
    sku_level2: str,
    unit_price: float,
    quantity: int,
    idempotency_key: str,
):
    """
    调用 POST /orders/create
    必须传入 X-Idempotency-Key 请求头
    """
    headers = {"X-Idempotency-Key": idempotency_key}
    payload = {
        "brandId": brand_id,
        "rechargeAccount": recharge_account,
        "skuLevel1": sku_level1,
        "skuLevel2": sku_level2,
        "unitPrice": unit_price,
        "quantity": quantity,
    }
    resp = session.post(
        f"{BASE_URL}/orders/create",
        json=payload,
        headers=headers,
        timeout=TIMEOUT,
    )
    return resp


def get_order_status(order_id: str):
    resp = session.get(f"{BASE_URL}/orders/{order_id}/status", timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def mock_pay_success(order_id: str):
    """模拟买家支付成功，触发 15 秒（DEBUG）自动退款计时器"""
    resp = session.post(f"{BASE_URL}/orders/{order_id}/mock-pay-success", timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def clear_debug_data():
    """清空内存数据，便于测试隔离"""
    try:
        session.get(f"{BASE_URL}/debug/clear", timeout=5)
    except Exception:
        pass


# =============================================================================
# 测试用例
# =============================================================================
def test_case_1_quantity_2_rejected(template: dict):
    """
    Case 1 (异常流):
    尝试下单购买数量为 2 的商品，验证服务器是否正确返回 400 并拦截。
    """
    print("=== Case 1: 购买数量为 2 应被拦截 ===")

    # 构造合法的 SKU 数据，但 quantity=2
    level1 = template["skuCascadeList"][0]["level1Name"]
    level2 = template["skuCascadeList"][0]["level2Options"][0]["durationOrAmount"]
    price = template["skuCascadeList"][0]["level2Options"][0]["bestPrice"]

    idem_key = f"case1-{uuid.uuid4()}"

    resp = create_order(
        brand_id=TEST_BRAND_ID,
        recharge_account=VALID_ACCOUNT,
        sku_level1=level1,
        sku_level2=level2,
        unit_price=price,
        quantity=2,
        idempotency_key=idem_key,
    )

    print(f"  状态码: {resp.status_code}")
    print(f"  返回内容: {resp.text}")

    assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}"
    assert "代充安全机制限制，单次交易仅支持购买 1 份" in resp.text, \
        "错误提示信息不符合预期"

    print("✅ Case 1 通过：数量=2 被正确拦截\n")


def test_case_2_invalid_account(template: dict):
    """
    Case 2 (异常流):
    尝试输入格式错误的充值账号，验证是否拦截。
    """
    print("=== Case 2: 格式错误的充值账号应被拦截 ===")

    level1 = template["skuCascadeList"][0]["level1Name"]
    level2 = template["skuCascadeList"][0]["level2Options"][0]["durationOrAmount"]
    price = template["skuCascadeList"][0]["level2Options"][0]["bestPrice"]

    idem_key = f"case2-{uuid.uuid4()}"

    resp = create_order(
        brand_id=TEST_BRAND_ID,
        recharge_account=INVALID_ACCOUNT,  # 格式错误
        sku_level1=level1,
        sku_level2=level2,
        unit_price=price,
        quantity=1,
        idempotency_key=idem_key,
    )

    print(f"  状态码: {resp.status_code}")
    print(f"  返回内容: {resp.text}")

    assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}"
    assert "充值账号格式不正确" in resp.text, "错误提示信息不符合预期"

    print("✅ Case 2 通过：非法账号被正确拦截\n")


def test_case_3_normal_create_order(template: dict):
    """
    Case 3 (正常流):
    传入合规参数、传入唯一幂等 X-Idempotency-Key 下单，验证订单创建成功。
    """
    print("=== Case 3: 合规参数正常下单 ===")

    level1 = template["skuCascadeList"][0]["level1Name"]
    level2 = template["skuCascadeList"][0]["level2Options"][0]["durationOrAmount"]
    price = template["skuCascadeList"][0]["level2Options"][0]["bestPrice"]

    idem_key = f"case3-{uuid.uuid4()}"

    resp = create_order(
        brand_id=TEST_BRAND_ID,
        recharge_account=VALID_ACCOUNT,
        sku_level1=level1,
        sku_level2=level2,
        unit_price=price,
        quantity=1,
        idempotency_key=idem_key,
    )

    print(f"  状态码: {resp.status_code}")
    data = resp.json()
    print(f"  返回数据: {data}")

    assert resp.status_code == 200, f"下单失败: {resp.text}"
    assert "orderId" in data, "响应中缺少 orderId"
    assert data["orderId"].startswith("ORD_"), "orderId 格式异常"
    assert "payUrl" in data, "响应中缺少 payUrl"

    # 额外验证：通过状态接口确认订单已创建
    status = get_order_status(data["orderId"])
    assert status["status"] == "PENDING_PAY", f"初始状态应为 PENDING_PAY，实际 {status['status']}"

    print(f"✅ Case 3 通过：订单 {data['orderId']} 创建成功\n")
    return data["orderId"]  # 返回订单号供后续用例参考（本用例独立）


def test_case_4_idempotency(template: dict):
    """
    Case 4 (幂等流):
    使用完全相同的 X-Idempotency-Key 再次请求下单，
    验证是否返回了相同的订单号（且没有产生新订单）。
    """
    print("=== Case 4: 幂等性校验（相同 Key 返回相同订单） ===")

    level1 = template["skuCascadeList"][0]["level1Name"]
    level2 = template["skuCascadeList"][0]["level2Options"][0]["durationOrAmount"]
    price = template["skuCascadeList"][0]["level2Options"][0]["bestPrice"]

    idem_key = f"case4-idempotent-{uuid.uuid4()}"

    # 第一次下单
    resp1 = create_order(
        brand_id=TEST_BRAND_ID,
        recharge_account=VALID_ACCOUNT,
        sku_level1=level1,
        sku_level2=level2,
        unit_price=price,
        quantity=1,
        idempotency_key=idem_key,
    )
    assert resp1.status_code == 200, "第一次下单失败"
    order1 = resp1.json()
    print(f"  第一次订单: {order1['orderId']}")

    # 第二次使用完全相同的幂等键
    resp2 = create_order(
        brand_id=TEST_BRAND_ID,
        recharge_account=VALID_ACCOUNT,
        sku_level1=level1,
        sku_level2=level2,
        unit_price=price,
        quantity=1,
        idempotency_key=idem_key,  # 相同 Key
    )
    assert resp2.status_code == 200, "第二次幂等请求失败"
    order2 = resp2.json()
    print(f"  第二次订单: {order2['orderId']}")

    # 核心断言：两次返回相同的 orderId
    assert order1["orderId"] == order2["orderId"], \
        f"幂等性失败：两次返回不同订单 {order1['orderId']} != {order2['orderId']}"

    # 额外验证：系统中实际只有这一个订单（可选，通过 debug 接口）
    debug_resp = session.get(f"{BASE_URL}/debug/orders", timeout=TIMEOUT)
    debug_data = debug_resp.json()
    orders_with_key = [o for o in debug_data["orders"] if o.get("idempotencyKey") == idem_key]
    assert len(orders_with_key) == 1, f"幂等键 {idem_key} 对应了多个订单"

    print("✅ Case 4 通过：幂等键生效，重复请求返回相同订单\n")


def test_case_5_auto_refund_timeout(template: dict):
    """
    Case 5 (超时退款流):
    开启 DEBUG_MODE=True，下单成功后模拟支付，
    等待约15秒，轮询验证订单状态是否自动由履约中状态变更为 REFUNDED。
    """
    print("=== Case 5: 15秒超时自动退款（DEBUG_MODE 加速） ===")

    level1 = template["skuCascadeList"][0]["level1Name"]
    level2 = template["skuCascadeList"][0]["level2Options"][0]["durationOrAmount"]
    price = template["skuCascadeList"][0]["level2Options"][0]["bestPrice"]

    idem_key = f"case5-timeout-{uuid.uuid4()}"

    # 1. 创建订单
    resp = create_order(
        brand_id=TEST_BRAND_ID,
        recharge_account=VALID_ACCOUNT,
        sku_level1=level1,
        sku_level2=level2,
        unit_price=price,
        quantity=1,
        idempotency_key=idem_key,
    )
    assert resp.status_code == 200
    order = resp.json()
    order_id = order["orderId"]
    print(f"  订单创建: {order_id}")

    # 2. 模拟支付成功（关键：启动后台 15 秒退款计时器）
    pay_result = mock_pay_success(order_id)
    print(f"  支付模拟成功，当前状态: {pay_result.get('status')}")

    # 3. 等待自动退款（DEBUG 模式下 15 秒）
    print(f"  等待自动退款（最多 {MAX_WAIT_FOR_REFUND} 秒）...")
    start = time.time()
    final_status = None

    while time.time() - start < MAX_WAIT_FOR_REFUND:
        status_info = get_order_status(order_id)
        final_status = status_info["status"]
        print(f"    当前状态: {final_status} ({status_info.get('statusText')})")

        if final_status == "REFUNDED":
            break
        time.sleep(POLL_INTERVAL)
    else:
        # 超时仍未退款
        assert False, f"等待 {MAX_WAIT_FOR_REFUND} 秒后订单仍未自动退款，最终状态: {final_status}"

    # 4. 最终断言
    assert final_status == "REFUNDED", f"期望 REFUNDED，实际 {final_status}"

    # 可选：确认没有凭证
    status_info = get_order_status(order_id)
    assert status_info.get("rechargeProofUrl") in (None, ""), "退款订单不应有充值凭证"

    print(f"✅ Case 5 通过：订单 {order_id} 已自动退款，状态 = {final_status}\n")


# =============================================================================
# 主流程
# =============================================================================
def main():
    print("=" * 60)
    print("虚拟商品代充值 Skill - 端到端自动化测试")
    print("=" * 60 + "\n")

    check_server_alive()
    clear_debug_data()

    # 准备动态测试数据（从真实模板获取，避免硬编码）
    brands = get_brands()
    print(f"服务可用，当前品牌数量: {len(brands)}")

    template = get_template(TEST_BRAND_ID)
    print(f"已加载品牌模板: {template['brandId']} ({template['inputFieldName']})")
    print()

    # 执行所有测试用例
    try:
        test_case_1_quantity_2_rejected(template)
        test_case_2_invalid_account(template)
        test_case_3_normal_create_order(template)
        test_case_4_idempotency(template)
        test_case_5_auto_refund_timeout(template)

        print("=" * 60)
        print("🎉 所有测试用例全部通过！")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生未预期错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
