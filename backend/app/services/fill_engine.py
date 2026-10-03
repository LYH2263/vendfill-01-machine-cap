"""Vending refill.

First pass:  gap = capacity - stock - in_transit; ideal fill = gap (满补).
Second pass: a machine-level cap (max_fill_qty) is distributed by 7-day sales,
high to low. Lanes that get nothing once the cap is exhausted keep fill_qty = 0
with status "capped" (整机件数已满) — never silently over-filled.

max_fill_qty <= 0 means unlimited, i.e. fill every lane to its gap (现网口径).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

# 状态取值：need_fill 待补 | full 单道满仓 | overbooked 单道超占 | capped 整机件数已满
STATUS_NEED = "need_fill"
STATUS_FULL = "full"
STATUS_OVERBOOKED = "overbooked"
STATUS_CAPPED = "capped"

# 每种状态对应的唯一原因文案；capped 只能写“整机件数已满”，不得与满仓/超占合并。
STATUS_REASONS = {
    STATUS_NEED: "待补",
    STATUS_FULL: "满仓",
    STATUS_OVERBOOKED: "超占",
    STATUS_CAPPED: "整机件数已满",
}


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
    sold_7d: int = 0
    reason: str = ""


def compute_gap(capacity: int, stock: int, in_transit: int) -> int:
    return capacity - stock - in_transit


def build_fill_lines(
    lanes: list[dict],
    requested: dict[int, int] | None = None,
    max_fill_qty: int = 0,
    sold_7d: dict[int, int] | None = None,
) -> list[FillLine]:
    """Build fill lines with one truncation rule shared by 补货单/汇总/点位页.

    requested: optional desired fill per lane_id; capped by gap; never negative.
    max_fill_qty: machine-wide total fill cap for one refill; <=0 = unlimited.
    sold_7d: per lane_id units sold in the last 7 days; desc tie-break by lane_id.
    """
    sold_7d = sold_7d or {}
    lines: list[FillLine] = []
    need: list[FillLine] = []

    # Pass 1 — per-lane gap gives the ideal fill.
    for lane in lanes:
        sold = int(sold_7d.get(lane["id"], 0))
        gap = compute_gap(int(lane["capacity"]), int(lane["stock"]), int(lane["in_transit"]))
        if gap < 0:
            status, fill = STATUS_OVERBOOKED, 0
        elif gap == 0:
            status, fill = STATUS_FULL, 0
        else:
            status, fill = STATUS_NEED, gap
            if requested is not None:
                fill = max(0, min(int(requested.get(lane["id"], gap)), gap))
        line = FillLine(
            lane_id=lane["id"], slot_no=lane["slot_no"], sku_name=lane["sku_name"],
            capacity=lane["capacity"], stock=lane["stock"], in_transit=lane["in_transit"],
            gap=gap, fill_qty=fill, status=status, sold_7d=sold,
            reason=STATUS_REASONS[status],
        )
        lines.append(line)
        if status == STATUS_NEED and fill > 0:
            need.append(line)

    # Pass 2 — machine cap distributed by 7-day sales (high -> low).
    # Unlimited when max_fill_qty <= 0; also skip when ideal total already fits.
    ideal_total = sum(l.fill_qty for l in need)
    if max_fill_qty and max_fill_qty > 0 and ideal_total > max_fill_qty:
        budget = max_fill_qty
        for line in sorted(need, key=lambda l: (-l.sold_7d, l.lane_id)):
            if budget <= 0:
                line.fill_qty = 0
                line.status = STATUS_CAPPED
                line.reason = STATUS_REASONS[STATUS_CAPPED]
            elif line.fill_qty <= budget:
                budget -= line.fill_qty  # high-sales lane eats its whole gap first
            else:
                line.fill_qty = budget
                budget = 0
        # Defensive guard: rounding/edge cases must never exceed the saved cap.
        assert sum(l.fill_qty for l in lines) <= max_fill_qty

    return lines


def summarize(lines: list[FillLine], max_fill_qty: int = 0) -> dict:
    return {
        "total_fill": sum(l.fill_qty for l in lines),
        "need_fill_count": sum(1 for l in lines if l.status == STATUS_NEED),
        "full_count": sum(1 for l in lines if l.status == STATUS_FULL),
        "overbooked_count": sum(1 for l in lines if l.status == STATUS_OVERBOOKED),
        "capped_count": sum(1 for l in lines if l.status == STATUS_CAPPED),
        "max_fill_qty": max_fill_qty,
        "lines": [asdict(l) for l in lines],
    }
