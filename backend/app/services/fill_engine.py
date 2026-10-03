"""Vending refill: gap = capacity - stock - in_transit; fills capped by gap; no negative fills.

Machine-wide cap (整机补货件数上限): ideal fills are computed per lane from the
gap first, then distributed to lanes by last-7-day sales (descending). Once the
machine cap is exhausted, remaining lanes get fill_qty 0 and are marked
"capped" with reason 整机件数已满 — never merged with 单道已满仓 / 单道超占.
Cap 0 means unlimited (fill by gap, same as before).
"""
from __future__ import annotations
from dataclasses import asdict, dataclass

REASON_FULL = "单道已满仓"
REASON_OVERBOOKED = "单道超占"
REASON_CAPPED = "整机件数已满"

@dataclass
class FillLine:
    lane_id: int
    slot_no: str
    sku_name: str
    capacity: int
    stock: int
    in_transit: int
    gap: int
    fill_qty: int
    status: str  # need_fill | full | overbooked | capped
    reason: str = ""  # human-readable cause for a zero/truncated fill

def compute_gap(capacity: int, stock: int, in_transit: int) -> int:
    return capacity - stock - in_transit

def build_fill_lines(lanes: list[dict], requested: dict[int, int] | None = None) -> list[FillLine]:
    """requested optional desired fill per lane_id; capped by gap; never negative."""
    lines: list[FillLine] = []
    for lane in lanes:
        gap = compute_gap(int(lane["capacity"]), int(lane["stock"]), int(lane["in_transit"]))
        if gap < 0:
            status = "overbooked"
            reason = REASON_OVERBOOKED
            fill = 0
        elif gap == 0:
            status = "full"
            reason = REASON_FULL
            fill = 0
        else:
            status = "need_fill"
            reason = ""
            desire = gap if requested is None else int(requested.get(lane["id"], gap))
            fill = max(0, min(desire, gap))
        lines.append(FillLine(
            lane_id=lane["id"], slot_no=lane["slot_no"], sku_name=lane["sku_name"],
            capacity=lane["capacity"], stock=lane["stock"], in_transit=lane["in_transit"],
            gap=gap, fill_qty=fill, status=status, reason=reason,
        ))
    return lines

def apply_machine_cap(lines: list[FillLine], max_total: int, sales_7d: dict[int, int] | None = None) -> list[FillLine]:
    """Truncate fills so the machine total never exceeds max_total (<= 0 means unlimited).

    Lanes are served highest last-7-day sales first (ties by slot_no for a
    stable order). A lane cut down to 0 by the machine cap is marked "capped"
    with reason 整机件数已满; full/overbooked lanes keep their own reason.
    """
    if max_total <= 0:
        return lines
    sales = sales_7d or {}
    budget = max_total
    queue = sorted(
        (l for l in lines if l.status == "need_fill" and l.fill_qty > 0),
        key=lambda l: (-int(sales.get(l.lane_id, 0)), l.slot_no),
    )
    for line in queue:
        if budget <= 0:
            line.fill_qty = 0
            line.status = "capped"
            line.reason = REASON_CAPPED
            continue
        take = min(line.fill_qty, budget)
        line.fill_qty = take
        budget -= take
    return lines

def summarize(lines: list[FillLine]) -> dict:
    return {
        "total_fill": sum(l.fill_qty for l in lines),
        "need_fill_count": sum(1 for l in lines if l.status == "need_fill"),
        "full_count": sum(1 for l in lines if l.status == "full"),
        "overbooked_count": sum(1 for l in lines if l.status == "overbooked"),
        "capped_count": sum(1 for l in lines if l.status == "capped"),
        "lines": [asdict(l) for l in lines],
    }

def plan_refill(lanes: list[dict], max_total: int = 0,
                sales_7d: dict[int, int] | None = None,
                requested: dict[int, int] | None = None) -> dict:
    """Single truncation path shared by refill order / summary / location pages."""
    cap = max(0, int(max_total))
    lines = build_fill_lines(lanes, requested)
    apply_machine_cap(lines, cap, sales_7d)
    return {**summarize(lines), "max_fill_total": cap}
