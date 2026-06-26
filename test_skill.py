"""
虚拟商品代充值 Skill 自动化测试脚本

启动: uvicorn src.app:app --host 127.0.0.1 --port 8000
运行: python test_skill.py
"""

import sys
import time
import uuid

import requests

BASE_URL = "http://localhost:8000"
TIMEOUT = 10
POLL_INTERVAL = 2
MAX_WAIT = 25

TEST_BRAND_ID = "brand_001"
VALID_ACCOUNT = "13800138000"
INVALID_ACCOUNT = "12345678901"

session = requests.Session()
session.headers.update({"User-Agent": "recharge-skill-test/1.0"})


def check_server_alive() -> None:
    try:
        resp = session.get(f"{BASE_URL}/brands", timeout=5)
        if resp.status_code != 200:
            raise RuntimeError(f"服务返回异常状态码: {resp.status_code}")
    except Exception as e:
        print(f"[FAIL] 无法连接到 Mock 服务 {BASE_URL}: {e}")
        sys.exit(1)


def get_template(brand_id: str):
    resp = session.get(f"{BASE_URL}/brands/{brand_id}/template", timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def create_order(template, quantity=1, account=VALID_ACCOUNT, unit_price=None, idem_key=None):
    level1 = template["skuCascadeList"][0]["level1Name"]
    level2 = template["skuCascadeList"][0]["level2Options"][0]["durationOrAmount"]
    price = unit_price if unit_price is not None else template["skuCascadeList"][0]["level2Options"][0]["bestPrice"]
    headers = {"X-Idempotency-Key": idem_key or f"test-{uuid.uuid4()}"}
    payload = {
        "brandId": TEST_BRAND_ID,
        "rechargeAccount": account,
        "skuLevel1": level1,
        "skuLevel2": level2,
        "unitPrice": price,
        "quantity": quantity,
    }
    return session.post(f"{BASE_URL}/orders/create", json=payload, headers=headers, timeout=TIMEOUT)


def get_status(order_id: str):
    resp = session.get(f"{BASE_URL}/orders/{order_id}/status", timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def mock_pay(order_id: str):
    return session.post(f"{BASE_URL}/orders/{order_id}/mock-pay-success", timeout=TIMEOUT)


def seller_accept(order_id: str):
    return session.post(f"{BASE_URL}/seller/orders/{order_id}/accept", timeout=TIMEOUT)


def seller_start(order_id: str):
    return session.post(f"{BASE_URL}/seller/orders/{order_id}/start-recharge", timeout=TIMEOUT)


def seller_deliver(order_id: str, proof_url=None):
    body = {}
    if proof_url:
        body["rechargeProofUrl"] = proof_url
    return session.post(f"{BASE_URL}/seller/orders/{order_id}/deliver", json=body, timeout=TIMEOUT)


def confirm_receipt(order_id: str):
    return session.post(f"{BASE_URL}/orders/{order_id}/confirm-receipt", timeout=TIMEOUT)


def clear_debug():
    try:
        session.get(f"{BASE_URL}/debug/clear", timeout=5)
    except Exception:
        pass


def test_case_1_quantity_rejected(template):
    print("=== Case 1: quantity=2 应被拦截 ===")
    resp = create_order(template, quantity=2)
    assert resp.status_code == 400
    assert "单次交易仅支持购买 1 份" in resp.text
    print("[OK] Case 1 通过\n")


def test_case_2_invalid_account(template):
    print("=== Case 2: 非法账号应被拦截 ===")
    resp = create_order(template, account=INVALID_ACCOUNT)
    assert resp.status_code == 400
    assert "充值账号格式不正确" in resp.text
    print("[OK] Case 2 通过\n")


def test_case_3_wrong_unit_price(template):
    print("=== Case 3: 错误 unitPrice 应被拦截 ===")
    good_price = template["skuCascadeList"][0]["level2Options"][0]["bestPrice"]
    resp = create_order(template, unit_price=good_price + 1)
    assert resp.status_code == 400
    assert "bestPrice" in resp.text
    print("[OK] Case 3 通过\n")


def test_case_4_normal_create(template):
    print("=== Case 4: 合规下单 ===")
    resp = create_order(template)
    assert resp.status_code == 200
    data = resp.json()
    assert "orderId" in data
    assert "payTimeoutSeconds" in data
    assert "fulfillmentTimeoutSeconds" in data
    assert get_status(data["orderId"])["status"] == "PENDING_PAY"
    print(f"[OK] Case 4 通过: {data['orderId']}\n")
    return data["orderId"]


def test_case_5_idempotency(template):
    print("=== Case 5: 幂等性 ===")
    idem = f"idem-{uuid.uuid4()}"
    r1 = create_order(template, idem_key=idem)
    r2 = create_order(template, idem_key=idem)
    assert r1.json()["orderId"] == r2.json()["orderId"]
    print("[OK] Case 5 通过\n")


def test_case_6_auto_refund(template):
    print("=== Case 6: 履约超时自动退款 ===")
    resp = create_order(template)
    order_id = resp.json()["orderId"]
    mock_pay(order_id).raise_for_status()
    final = None
    start = time.time()
    while time.time() - start < MAX_WAIT:
        final = get_status(order_id)["status"]
        if final == "REFUNDED":
            break
        time.sleep(POLL_INTERVAL)
    assert final == "REFUNDED", f"期望 REFUNDED，实际 {final}"
    print("[OK] Case 6 通过\n")


def test_case_7_full_seller_flow(template):
    print("=== Case 7: 完整卖家履约流 DELIVERED ===")
    order_id = create_order(template).json()["orderId"]
    mock_pay(order_id).raise_for_status()
    seller_accept(order_id).raise_for_status()
    assert get_status(order_id)["status"] == "PENDING_ACCEPT"
    seller_start(order_id).raise_for_status()
    assert get_status(order_id)["status"] == "RECHARGING"
    seller_deliver(order_id).raise_for_status()
    st = get_status(order_id)
    assert st["status"] == "DELIVERED"
    assert st.get("rechargeProofUrl")
    assert st.get("autoConfirmTime")
    print("[OK] Case 7 通过\n")
    return order_id


def test_case_8_manual_confirm(template):
    print("=== Case 8: 买家手动确认收货 ===")
    order_id = test_case_7_full_seller_flow(template)
    resp = confirm_receipt(order_id)
    assert resp.status_code == 200
    assert get_status(order_id)["status"] == "COMPLETED"
    print("[OK] Case 8 通过\n")


def test_case_9_auto_confirm(template):
    print("=== Case 9: 自动确认收货 (DEBUG 5s) ===")
    order_id = create_order(template).json()["orderId"]
    mock_pay(order_id).raise_for_status()
    seller_accept(order_id).raise_for_status()
    seller_start(order_id).raise_for_status()
    seller_deliver(order_id).raise_for_status()
    final = None
    start = time.time()
    while time.time() - start < MAX_WAIT:
        final = get_status(order_id)["status"]
        if final == "COMPLETED":
            break
        time.sleep(POLL_INTERVAL)
    assert final == "COMPLETED", f"期望 COMPLETED，实际 {final}"
    print("[OK] Case 9 通过\n")


def main():
    print("=" * 60)
    print("虚拟商品代充值 Skill - 端到端测试")
    print("=" * 60 + "\n")
    check_server_alive()
    clear_debug()
    template = get_template(TEST_BRAND_ID)

    try:
        test_case_1_quantity_rejected(template)
        test_case_2_invalid_account(template)
        test_case_3_wrong_unit_price(template)
        test_case_4_normal_create(template)
        test_case_5_idempotency(template)
        test_case_6_auto_refund(template)
        clear_debug()
        test_case_7_full_seller_flow(template)
        clear_debug()
        test_case_8_manual_confirm(template)
        clear_debug()
        test_case_9_auto_confirm(template)
        print("=" * 60)
        print("[OK] 所有测试用例全部通过！")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n[FAIL] 测试失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
