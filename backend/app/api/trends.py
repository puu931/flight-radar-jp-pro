from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import PriceHistory, RoundTripHistory
from ..schemas import TrendPoint

router = APIRouter()


@router.get("", response_model=list[TrendPoint])
def trends(
    origin: str = Query(...),
    destination: str = Query(...),
    departure_date: Optional[str] = Query(None, description="YYYY-MM-DD; one_way only"),
    airline: Optional[str] = Query(None),
    days_back: int = Query(60, le=365),
    mode: str = Query("round_trip", pattern="^(one_way|round_trip)$"),
    db: Session = Depends(get_db),
) -> list[TrendPoint]:
    cutoff = datetime.utcnow() - timedelta(days=days_back)
    if mode == "round_trip":
        stmt = (
            select(RoundTripHistory)
            .where(RoundTripHistory.origin == origin)
            .where(RoundTripHistory.destination == destination)
            .where(RoundTripHistory.recorded_at >= cutoff)
            .order_by(RoundTripHistory.recorded_at.asc())
        )
        rows = db.execute(stmt).scalars().all()
        return [TrendPoint(recorded_at=r.recorded_at, min_price_twd=r.min_total_twd) for r in rows]

    stmt = (
        select(PriceHistory)
        .where(PriceHistory.origin == origin)
        .where(PriceHistory.destination == destination)
        .where(PriceHistory.recorded_at >= cutoff)
    )
    if departure_date:
        stmt = stmt.where(PriceHistory.departure_date == departure_date)
    if airline:
        stmt = stmt.where(PriceHistory.airline == airline)
    stmt = stmt.order_by(PriceHistory.recorded_at.asc())
    rows = db.execute(stmt).scalars().all()
    return [TrendPoint(recorded_at=r.recorded_at, min_price_twd=r.min_price_twd) for r in rows]
