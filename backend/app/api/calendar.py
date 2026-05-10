from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Flight
from ..schemas import CalendarCell

router = APIRouter()


@router.get("", response_model=list[CalendarCell])
def calendar(
    origin: str = Query(...),
    destination: str = Query(...),
    days: int = Query(90, le=365),
    db: Session = Depends(get_db),
) -> list[CalendarCell]:
    today = datetime.utcnow().date()
    end = today + timedelta(days=days)

    stmt = (
        select(
            func.date(Flight.departure_at).label("d"),
            func.min(Flight.price_twd).label("min_price"),
            func.count(Flight.id).label("cnt"),
        )
        .where(Flight.origin == origin)
        .where(Flight.destination == destination)
        .where(Flight.departure_at >= datetime.combine(today, datetime.min.time()))
        .where(Flight.departure_at < datetime.combine(end, datetime.min.time()))
        .group_by("d")
        .order_by("d")
    )
    rows = db.execute(stmt).all()
    return [
        CalendarCell(date=str(r.d), min_price_twd=float(r.min_price), flight_count=int(r.cnt))
        for r in rows
    ]
