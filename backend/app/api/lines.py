from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Line
router = APIRouter(prefix="/lines", tags=["lines"])

class LineUpdate(BaseModel):
    min_turnaround_min: float | None = None

def line_dict(r: Line) -> dict:
    return {"id": r.id, "code": r.code, "name": r.name, "planned_headway_min": r.planned_headway_min,
            "bunch_threshold": r.bunch_threshold, "large_threshold": r.large_threshold,
            "min_turnaround_min": r.min_turnaround_min}

@router.get("")
def list_lines(db: Session = Depends(get_db)):
    rows = db.scalars(select(Line).order_by(Line.id)).all()
    return [line_dict(r) for r in rows]

@router.patch("/{line_id}")
def update_line(line_id: int, body: LineUpdate, db: Session = Depends(get_db)):
    line = db.get(Line, line_id)
    if not line: raise HTTPException(404, "线路不存在")
    if body.min_turnaround_min is not None and body.min_turnaround_min < 0:
        raise HTTPException(400, "最小折返分钟不能为负")
    line.min_turnaround_min = body.min_turnaround_min
    db.commit(); db.refresh(line)
    return line_dict(line)
