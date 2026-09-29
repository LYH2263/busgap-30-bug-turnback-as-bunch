"""Bus bunching: planned headway vs actual arrival gaps."""
from __future__ import annotations
from dataclasses import asdict, dataclass

@dataclass
class GapEvent:
    stop_name: str
    earlier_trip: str
    later_trip: str
    gap_min: float
    planned_headway_min: float
    status: str
    suggestion: str

def classify_gap(gap_min: float, planned_headway_min: float, bunch_threshold: float, large_threshold: float) -> tuple[str, str]:
    if gap_min < bunch_threshold:
        return ("bunching", f"间隔 {gap_min:.1f} 分钟低于串车阈值 {bunch_threshold}，建议后车缓行或抽稀。")
    if gap_min > large_threshold:
        return ("large_gap", f"间隔 {gap_min:.1f} 分钟超过大间隔阈值 {large_threshold}，建议前车减速或加发。")
    return ("normal", f"间隔接近计划 {planned_headway_min:.1f} 分钟，保持即可。")

def classify_turnaround(gap_min: float, min_turnaround_min: float, vehicle_no: str) -> tuple[str, str]:
    # 折返不足单独成档：建议只谈折返，不再催串车缓行/抽稀
    return ("short_turnaround",
            f"同车 {vehicle_no} 在终点站的接续间隔仅 {gap_min:.1f} 分钟，"
            f"小于最小折返 {min_turnaround_min:g} 分钟，属折返不足；"
            f"建议安排足时折返或调整该接续班次。")

def turnaround_should_surface(min_turnaround_min: float | None) -> bool:
    return min_turnaround_min is not None and min_turnaround_min > 0

def is_short_turnaround(prev: dict, cur: dict, terminal_seq: int | None, min_turnaround_min: float | None, gap_min: float) -> bool:
    # 没配最小折返分钟时与底座（普通间隔分档）保持一致
    if not turnaround_should_surface(min_turnaround_min):
        return False
    # 必须是同一辆车的终点接续；车号缺失时不做同车认定
    prev_vehicle = prev.get("vehicle_no")
    cur_vehicle = cur.get("vehicle_no")
    if not prev_vehicle or prev_vehicle != cur_vehicle:
        return False
    # 两班都记在终点站（最大站序）才算折返
    if terminal_seq is None:
        return False
    if prev.get("stop_seq") != terminal_seq or cur.get("stop_seq") != terminal_seq:
        return False
    return gap_min < min_turnaround_min

def detect_bunching(arrivals: list[dict], planned_headway_min: float, bunch_threshold: float, large_threshold: float,
                    min_turnaround_min: float | None = None) -> list[GapEvent]:
    seqs = [a["stop_seq"] for a in arrivals if a.get("stop_seq") is not None]
    terminal_seq = max(seqs) if seqs else None
    by_stop: dict[str, list[dict]] = {}
    for a in arrivals:
        by_stop.setdefault(a["stop_name"], []).append(a)
    events: list[GapEvent] = []
    for stop, items in by_stop.items():
        items = sorted(items, key=lambda x: x["actual_arrive"])
        for i in range(1, len(items)):
            prev, cur = items[i - 1], items[i]
            gap_min = (cur["actual_arrive"] - prev["actual_arrive"]).total_seconds() / 60.0
            if is_short_turnaround(prev, cur, terminal_seq, min_turnaround_min, gap_min):
                status, suggestion = classify_turnaround(gap_min, min_turnaround_min, prev["vehicle_no"])
            else:
                # 折返分钟够（或未配置、非同车、非终点）的接续一律走普通间隔分档，保留该段事件
                status, suggestion = classify_gap(gap_min, planned_headway_min, bunch_threshold, large_threshold)
            events.append(GapEvent(stop, prev["trip_no"], cur["trip_no"], round(gap_min, 2), planned_headway_min, status, suggestion))
    return events

def events_to_dicts(events: list[GapEvent]) -> list[dict]:
    return [asdict(e) for e in events]
