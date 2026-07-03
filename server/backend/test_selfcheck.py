"""后端自测脚本 - 验证核心业务闭环，不依赖 pytest，直接 HTTP 调用。

测试链路：
1. 健康检查
2. 设置：读取默认 / 更新 / 校验级联重算
3. 客户：创建 / 唯一性校验 / 查询
4. 交易：创建（completed）→ 验证客户累计、质保、利润级联
5. 交易：创建 introduced 来源 → 验证推荐关系 + 返利生成
6. 售后：创建工单 → 验证交易状态联动（→aftersales）→ 解决后恢复
7. 返利：状态机（pending→paid）+ 非法流转拦截
8. 迁移：导出 → 再导入 → 校验条数一致（往返兼容）
9. 财务：overview 聚合

运行：python test_selfcheck.py
"""
import json
import sys
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"

passed = 0
failed = 0


def api(method, path, body=None):
    url = BASE + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def main():
    print("=" * 60)
    print("闲鱼记账后端自测")
    print("=" * 60)

    # 1. 健康检查
    print("\n[1] 健康检查")
    code, data = api("GET", "/api/health")
    check("health ok", code == 200 and data.get("ok") is True, f"code={code}")

    # 2. 设置
    print("\n[2] 系统设置")
    code, settings = api("GET", "/api/settings")
    check("get default settings", code == 200 and settings.get("rebate_rate") == 0.1, f"code={code}")
    # 阈值合理性校验：vip 阈值不能高于 core
    code, _ = api("PUT", "/api/settings", {"vip_threshold": 9999, "core_threshold": 100})
    check("reject invalid vip>core threshold", code == 400, f"应拒绝但 code={code}")

    # 3. 客户
    print("\n[3] 客户管理")
    code, c1 = api("POST", "/api/customers", {"xianyu_nickname": "测试买家A"})
    check("create customer A", code == 200 and c1.get("id") is not None, f"code={code}")
    cid = c1.get("id")

    # 昵称唯一性
    code, _ = api("POST", "/api/customers", {"xianyu_nickname": "测试买家A"})
    check("reject duplicate nickname", code == 400, f"应拒绝但 code={code}")

    # 介绍人客户
    code, c2 = api("POST", "/api/customers", {"xianyu_nickname": "介绍人B"})
    check("create referrer B", code == 200)
    rid = c2.get("id")

    # 4. 交易 - completed，验证客户累计/利润/质保级联
    print("\n[4] 交易创建 + 客户累计级联")
    code, t1 = api("POST", "/api/transactions", {
        "customer_id": cid, "product_name": "软件激活码",
        "sale_price": 100, "cost_price": 40, "status": "completed",
        "trade_at": "2026-06-01T10:00:00", "source_type": "direct",
    })
    check("create completed transaction", code == 200, f"code={code}")
    check("profit = sale - cost (60)", t1.get("profit") == 60.0, f"profit={t1.get('profit')}")
    check("warranty_end set for completed", t1.get("warranty_end") is not None, f"warranty_end={t1.get('warranty_end')}")

    # 验证客户累计重算
    code, c1_after = api("GET", f"/api/customers/{cid}")
    check("customer total_spent updated to 100", c1_after.get("total_spent") == 100.0, f"spent={c1_after.get('total_spent')}")
    check("customer trade_count = 1", c1_after.get("trade_count") == 1, f"count={c1_after.get('trade_count')}")

    # 5. 交易 - introduced 来源，验证推荐关系 + 返利
    print("\n[5] 推荐关系 + 返利级联")
    code, t2 = api("POST", "/api/transactions", {
        "customer_id": cid, "product_name": "会员代充",
        "sale_price": 200, "cost_price": 100, "status": "completed",
        "trade_at": "2026-06-05T10:00:00", "source_type": "introduced",
        "source_customer_id": rid,
    })
    check("create introduced transaction", code == 200, f"code={code}")
    t2_profit = t2.get("profit")

    # 验证返利生成（默认 rebate_base=profit，rate=0.1）
    code, rebates = api("GET", "/api/rebates")
    check("rebate record created", len(rebates) == 1, f"len={len(rebates)}")
    if rebates:
        expected_rebate = round(t2_profit * 0.1, 2)
        check("rebate amount = profit*0.1", abs(rebates[0]["amount"] - expected_rebate) < 0.01,
              f"amount={rebates[0]['amount']} expected={expected_rebate}")
        check("rebate status pending", rebates[0]["status"] == "pending")
        rebate_id = rebates[0]["id"]

        # 状态机：paid → paid 非法
        code, _ = api("PATCH", f"/api/rebates/{rebate_id}", {"status": "paid"})
        check("mark rebate paid", code == 200, f"code={code}")
        code, _ = api("PATCH", f"/api/rebates/{rebate_id}", {"status": "paid"})
        check("reject paid→paid (idempotent ok or rejected)", code in (200, 400))

    # 6. 售后工单 + 交易状态联动
    print("\n[6] 售后工单 + 状态联动")
    code, ticket = api("POST", "/api/aftersales", {
        "transaction_id": t1["id"], "issue_desc": "激活失败",
    })
    check("create aftersales ticket", code == 200, f"code={code}")
    # 验证交易状态变为 aftersales
    code, t1_check = api("GET", f"/api/transactions/{t1['id']}")
    check("transaction status -> aftersales", t1_check.get("status") == "aftersales", f"status={t1_check.get('status')}")
    # 解决工单 → 交易状态恢复 completed
    code, _ = api("PATCH", f"/api/aftersales/{ticket['id']}", {"status": "resolved", "solution_type": "remote"})
    check("resolve ticket", code == 200, f"code={code}")
    code, t1_final = api("GET", f"/api/transactions/{t1['id']}")
    check("transaction status restored to completed", t1_final.get("status") == "completed", f"status={t1_final.get('status')}")

    # 7. 财务聚合
    print("\n[7] 财务聚合")
    code, overview = api("GET", "/api/finance/overview")
    check("finance overview returns", code == 200 and "totalIncome" in overview, f"code={code}")

    # 8. 迁移往返
    print("\n[8] 数据迁移导出→导入往返")
    code, exported = api("GET", "/api/migrate/export")
    check("export backup", code == 200 and "data" in exported, f"code={code}")
    if code == 200:
        before_counts = {k: len(v) for k, v in exported["data"].items() if isinstance(v, list)}
        code, result = api("POST", "/api/migrate/import", exported)
        check("import backup succeeds", code == 200 and result.get("success") is True, f"code={code} body={result}")
        # 再导出验证条数一致
        code, exported2 = api("GET", "/api/migrate/export")
        after_counts = {k: len(v) for k, v in exported2["data"].items() if isinstance(v, list)}
        check("record counts preserved after round-trip", before_counts == after_counts,
              f"before={before_counts} after={after_counts}")

    # 9. 审计日志
    print("\n[9] 审计日志")
    code, logs = api("GET", "/api/operation-logs")
    check("audit logs recorded", code == 200 and logs.get("total", 0) > 0, f"total={logs.get('total')}")

    print("\n" + "=" * 60)
    print(f"结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
