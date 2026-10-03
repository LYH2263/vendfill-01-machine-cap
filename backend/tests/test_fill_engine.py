from app.services.fill_engine import STATUS_CAPPED, STATUS_FULL, STATUS_NEED, STATUS_OVERBOOKED
from app.services.fill_engine import build_fill_lines, compute_gap, summarize

def _lane(id, cap, stock, transit):
    return {"id": id, "slot_no": f"A{id}", "sku_name": f"SKU{id}",
            "capacity": cap, "stock": stock, "in_transit": transit}

def test_gap_basic():
    assert compute_gap(20, 5, 0) == 15
    assert compute_gap(20, 10, 5) == 5

def test_no_negative_fill():
    lines = build_fill_lines([_lane(1, 10, 12, 0)])
    assert lines[0].fill_qty == 0
    assert lines[0].status == STATUS_OVERBOOKED
    assert lines[0].reason == "超占"

def test_cap_by_gap():
    lines = build_fill_lines([_lane(1, 20, 5, 0)], requested={1: 100})
    assert lines[0].fill_qty == 15
    assert lines[0].gap == 15

def test_full_zero_fill():
    s = summarize(build_fill_lines([_lane(1, 10, 8, 2)]))
    assert s["full_count"] == 1
    assert s["total_fill"] == 0

def test_zero_means_unlimited_fills_to_gap():
    # 上限 0 = 不限制，行为与现网按缺口满补相同。
    lanes = [_lane(1, 20, 5, 0), _lane(2, 10, 0, 0)]
    s = summarize(build_fill_lines(lanes, max_fill_qty=0), max_fill_qty=0)
    assert s["total_fill"] == 25
    assert s["capped_count"] == 0
    assert s["max_fill_qty"] == 0

def test_cap_distributes_by_sales_high_first():
    # 缺口：道1=10(销量低), 道2=10(销量高), 道3=10(无销量)；理想 30，上限 15。
    lanes = [_lane(1, 10, 0, 0), _lane(2, 10, 0, 0), _lane(3, 10, 0, 0)]
    lines = build_fill_lines(lanes, max_fill_qty=15, sold_7d={1: 3, 2: 9, 3: 0})
    by = {l.lane_id: l for l in lines}
    # 高销量道先吃满（10），再用剩余预算 5；最低销量道补 0。
    assert by[2].fill_qty == 10 and by[2].status == STATUS_NEED
    assert by[1].fill_qty == 5 and by[1].status == STATUS_NEED
    assert by[3].fill_qty == 0 and by[3].status == STATUS_CAPPED
    s = summarize(lines, max_fill_qty=15)
    assert s["total_fill"] == 15
    assert s["capped_count"] == 1
    # 绝不超发
    assert sum(l.fill_qty for l in lines) <= 15

def test_cap_exactly_equals_total_gap():
    lanes = [_lane(1, 10, 5, 0), _lane(2, 10, 5, 0)]  # 缺口各 5，合计 10
    lines = build_fill_lines(lanes, max_fill_qty=10, sold_7d={1: 1, 2: 2})
    assert summarize(lines)["total_fill"] == 10
    assert all(l.status == STATUS_NEED for l in lines)

def test_cap_larger_than_total_gap_fills_all():
    # 全机缺口不足上限时，按缺口满补，总量小于上限。
    lanes = [_lane(1, 10, 8, 0)]  # 缺口 2
    lines = build_fill_lines(lanes, max_fill_qty=20)
    assert summarize(lines)["total_fill"] == 2
    assert lines[0].status == STATUS_NEED

def test_capped_reason_is_standalone():
    # 被整机上限截成 0 的货道，原因只能是“整机件数已满”，不得与满仓/超占合并。
    lanes = [_lane(1, 10, 0, 0), _lane(2, 10, 0, 0)]
    lines = build_fill_lines(lanes, max_fill_qty=5, sold_7d={1: 9, 2: 1})
    capped = next(l for l in lines if l.status == STATUS_CAPPED)
    assert capped.fill_qty == 0
    assert capped.reason == "整机件数已满"
    assert capped.reason != "满仓" and capped.reason != "超占"

def test_full_and_overbooked_unaffected_by_cap():
    lanes = [_lane(1, 10, 10, 0), _lane(2, 10, 12, 0), _lane(3, 10, 0, 0)]
    lines = build_fill_lines(lanes, max_fill_qty=3, sold_7d={3: 1})
    by = {l.lane_id: l for l in lines}
    assert by[1].status == STATUS_FULL
    assert by[2].status == STATUS_OVERBOOKED
    assert by[3].status == STATUS_NEED and by[3].fill_qty == 3

def test_sales_tie_break_is_stable_by_lane_id():
    lanes = [_lane(2, 10, 0, 0), _lane(1, 10, 0, 0)]
    lines = build_fill_lines(lanes, max_fill_qty=10, sold_7d={1: 5, 2: 5})
    by = {l.lane_id: l for l in lines}
    assert by[1].fill_qty == 10
    assert by[2].status == STATUS_CAPPED
