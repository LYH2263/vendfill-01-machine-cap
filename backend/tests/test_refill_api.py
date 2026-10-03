from conftest import make_location


def test_locations_expose_max_fill_qty(client):
    loc_id = make_location(20)
    rows = client.get("/api/locations").json()
    me = next(r for r in rows if r["id"] == loc_id)
    assert me["max_fill_qty"] == 20


def test_negative_cap_rejected_and_everything_stays(client):
    loc_id = make_location(20)
    # 先落一张按 20 截断的单
    before = client.post(f"/api/refills/run?location_id={loc_id}").json()
    assert before["max_fill_qty"] == 20
    assert before["total_fill"] == 20

    # 负数拒绝保存（400）
    resp = client.patch(f"/api/locations/{loc_id}", json={"max_fill_qty": -1})
    assert resp.status_code == 400

    # 点位页读到的仍是改前的 20（没有半成功）
    rows = client.get("/api/locations").json()
    assert next(r for r in rows if r["id"] == loc_id)["max_fill_qty"] == 20

    # 下一次落单仍按保存当下的旧上限 20 重算，单上不会出现“新上限/旧总分”错配
    after = client.post(f"/api/refills/run?location_id={loc_id}").json()
    assert after["max_fill_qty"] == 20
    assert after["total_fill"] == 20


def test_seed_like_cap_20_high_sales_first_and_total_20(client):
    loc_id = make_location(20)
    data = client.post(f"/api/refills/run?location_id={loc_id}").json()

    by_slot = {l["slot_no"]: l for l in data["lines"]}
    # 高销量道 C1(销6)、B1(销4) 先吃满各 10；最低销量 A1(销2) 被整机上限截成 0
    assert by_slot["C1"]["fill_qty"] == 10 and by_slot["C1"]["status"] == "need_fill"
    assert by_slot["B1"]["fill_qty"] == 10 and by_slot["B1"]["status"] == "need_fill"
    assert by_slot["A1"]["fill_qty"] == 0 and by_slot["A1"]["status"] == "capped"
    assert by_slot["A1"]["reason"] == "整机件数已满"
    # 满仓/超占原因不得与整机截断并句
    assert by_slot["A2"]["reason"] == "满仓"
    assert by_slot["C2"]["reason"] == "超占"

    # 汇总总补件数必须等于 20，且与补货单逐行相加一致
    assert data["total_fill"] == 20
    assert sum(l["fill_qty"] for l in data["lines"]) == data["total_fill"]
    assert data["capped_count"] == 1


def test_summary_and_refill_share_one_truncation(client):
    loc_id = make_location(20)
    client.post(f"/api/refills/run?location_id={loc_id}")
    summary = client.get(f"/api/refills/summary?location_id={loc_id}").json()
    assert summary["total_fill"] == 20
    assert summary["max_fill_qty"] == 20
    assert summary["capped_count"] == 1

    # 满仓页只含单道满仓，不含被整机截成 0 的 A1
    full = client.get(f"/api/refills/full?location_id={loc_id}").json()["lanes"]
    slots = {l["slot_no"] for l in full}
    assert "A1" not in slots
    assert {"A2", "B2"} <= slots


def test_change_cap_takes_effect_on_next_run(client):
    loc_id = make_location(20)
    first = client.post(f"/api/refills/run?location_id={loc_id}").json()
    assert first["total_fill"] == 20

    # 改成不限制，下一次落单按保存当下读到的 0 重算，不沿用旧总分 20
    client.patch(f"/api/locations/{loc_id}", json={"max_fill_qty": 0})
    second = client.post(f"/api/refills/run?location_id={loc_id}").json()
    assert second["max_fill_qty"] == 0
    assert second["total_fill"] == 35  # 缺口合计 15+10+10
    by_slot = {l["slot_no"]: l for l in second["lines"]}
    assert by_slot["A1"]["fill_qty"] == 15 and by_slot["A1"]["status"] == "need_fill"

    # 离开点位页再进仍是新值（持久化）
    rows = client.get("/api/locations").json()
    assert next(r for r in rows if r["id"] == loc_id)["max_fill_qty"] == 0


def test_cap_persists_across_re_reads(client):
    loc_id = make_location(0)
    client.patch(f"/api/locations/{loc_id}", json={"max_fill_qty": 8})
    # 再次读取仍为 8
    rows = client.get("/api/locations").json()
    assert next(r for r in rows if r["id"] == loc_id)["max_fill_qty"] == 8
    data = client.post(f"/api/refills/run?location_id={loc_id}").json()
    # 上限 8：最高销量 C1 拿 8，其余待补道为 0；总量严格不超发
    by_slot = {l["slot_no"]: l for l in data["lines"]}
    assert by_slot["C1"]["fill_qty"] == 8
    assert by_slot["B1"]["status"] == "capped" and by_slot["A1"]["status"] == "capped"
    assert data["total_fill"] == 8
    assert sum(l["fill_qty"] for l in data["lines"]) == 8
