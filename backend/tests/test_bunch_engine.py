from datetime import datetime, timedelta
from app.services.bunch_engine import classify_gap, detect_bunching

def test_classify_bunching():
    assert classify_gap(2.0, 8.0, 3.0, 15.0)[0] == "bunching"

def test_classify_large():
    assert classify_gap(16.0, 8.0, 3.0, 15.0)[0] == "large_gap"

def test_classify_normal():
    assert classify_gap(8.0, 8.0, 3.0, 15.0)[0] == "normal"

def test_detect_bunching_events():
    base = datetime(2026, 1, 1, 8, 0)
    arrivals = [
        {"stop_name": "A", "trip_no": "T1", "actual_arrive": base},
        {"stop_name": "A", "trip_no": "T2", "actual_arrive": base + timedelta(minutes=2)},
        {"stop_name": "A", "trip_no": "T3", "actual_arrive": base + timedelta(minutes=20)},
    ]
    events = detect_bunching(arrivals, 8.0, 3.0, 15.0)
    assert len(events) == 2
    assert events[0].status == "bunching"
    assert events[1].status == "large_gap"

def _terminal_pair(gap_min: float, prev_vehicle="V1", cur_vehicle="V1", seq=1):
    base = datetime(2026, 1, 1, 8, 0)
    return [
        {"stop_name": "终点", "stop_seq": seq, "trip_no": "T1", "vehicle_no": prev_vehicle, "actual_arrive": base},
        {"stop_name": "终点", "stop_seq": seq, "trip_no": "T2", "vehicle_no": cur_vehicle, "actual_arrive": base + timedelta(minutes=gap_min)},
    ]

def test_same_vehicle_short_turnaround():
    events = detect_bunching(_terminal_pair(2.0), 8.0, 3.0, 15.0, min_turnaround_min=6.0)
    assert events[0].status == "short_turnaround"
    assert "折返" in events[0].suggestion
    assert "串车" not in events[0].suggestion

def test_same_vehicle_enough_turnaround_uses_headway_thresholds():
    # 折返足够（7 >= 6），同车接续仍按现网间隔阈值判定
    events = detect_bunching(_terminal_pair(7.0), 8.0, 3.0, 15.0, min_turnaround_min=6.0)
    assert events[0].status == "normal"
    # 折返足够但间隔本身触串车阈值时，仍判串车
    events = detect_bunching(_terminal_pair(2.0), 8.0, 3.0, 15.0, min_turnaround_min=1.0)
    assert events[0].status == "bunching"

def test_different_vehicles_not_turnaround():
    events = detect_bunching(_terminal_pair(2.0, cur_vehicle="V2"), 8.0, 3.0, 15.0, min_turnaround_min=6.0)
    assert events[0].status == "bunching"

def test_no_turnaround_config_unchanged():
    events = detect_bunching(_terminal_pair(2.0), 8.0, 3.0, 15.0)
    assert events[0].status == "bunching"

def test_non_terminal_stop_not_turnaround():
    base = datetime(2026, 1, 1, 8, 0)
    arrivals = [
        {"stop_name": "中途", "stop_seq": 0, "trip_no": "T1", "vehicle_no": "V1", "actual_arrive": base},
        {"stop_name": "中途", "stop_seq": 0, "trip_no": "T2", "vehicle_no": "V1", "actual_arrive": base + timedelta(minutes=2)},
        {"stop_name": "终点", "stop_seq": 1, "trip_no": "T1", "vehicle_no": "V1", "actual_arrive": base + timedelta(minutes=30)},
    ]
    events = detect_bunching(arrivals, 8.0, 3.0, 15.0, min_turnaround_min=6.0)
    assert len(events) == 1
    assert events[0].status == "bunching"

def test_seed_same_vehicle_short_terminal_continuation():
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from app.database import Base
    from app.models.models import Arrival, Line, Trip
    from app.services.seed import seed_if_empty

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        seed_if_empty(db)
        line = db.scalar(select(Line))
        trips = db.scalars(select(Trip)).all()
        trip_map = {t.id: t for t in trips}
        arrivals = db.scalars(select(Arrival)).all()
        payload = [{"stop_name": a.stop_name, "stop_seq": a.stop_seq, "trip_no": trip_map[a.trip_id].trip_no,
                    "vehicle_no": trip_map[a.trip_id].vehicle_no, "actual_arrive": a.actual_arrive} for a in arrivals]
        events = detect_bunching(payload, line.planned_headway_min, line.bunch_threshold, line.large_threshold,
                                 line.min_turnaround_min)
    finally:
        db.close()
    turn = [e for e in events if e.status == "short_turnaround"]
    assert len(turn) == 1
    assert turn[0].stop_name == "终点站"
    assert (turn[0].earlier_trip, turn[0].later_trip) == ("T04", "T05")
    assert "折返" in turn[0].suggestion
    # 同一对班次不得再被当作普通串车
    assert not any(e.earlier_trip == "T04" and e.later_trip == "T05" and e.status == "bunching" for e in events)
