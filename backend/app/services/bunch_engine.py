"""Bus bunching: planned headway vs actual arrival gaps."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime

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
    return ("short_turnaround",
            f"同车 {vehicle_no} 终点折返仅 {gap_min:.1f} 分钟，短于最小折返 {min_turnaround_min:.1f} 分钟，"
            f"建议优先保证折返时间，延长折返接续，勿再催后车缓行或抽稀。")

def is_short_turnaround(prev: dict, cur: dict, terminal_seq: int | None, min_turnaround_min: float | None, gap_min: float) -> bool:
    if not turnaround_should_surface(min_turnaround_min):
        return False
    if terminal_seq is None or prev.get("stop_seq") != terminal_seq:
        return False
    prev_vehicle, cur_vehicle = prev.get("vehicle_no") or "", cur.get("vehicle_no") or ""
    if not prev_vehicle or prev_vehicle != cur_vehicle:
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
                status, suggestion = classify_gap(gap_min, planned_headway_min, bunch_threshold, large_threshold)
            events.append(GapEvent(stop, prev["trip_no"], cur["trip_no"], round(gap_min, 2), planned_headway_min, status, suggestion))
    return events

def events_to_dicts(events: list[GapEvent]) -> list[dict]:
    return [asdict(e) for e in events]

# topic helpers for report assembly

def force_bunch_wording(gap_min: float, bunch_threshold: float) -> tuple[str, str]:
    return ("bunching", f"间隔 {gap_min:.1f} 分钟低于串车阈值 {bunch_threshold}，建议后车缓行或抽稀。")

def turnaround_should_surface(min_turnaround_min: float | None) -> bool:
    return min_turnaround_min is not None and min_turnaround_min > 0

