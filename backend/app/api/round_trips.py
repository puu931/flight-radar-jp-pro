from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import RoundTrip

router = APIRouter()


class RoundTripOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    origin: str
    destination: str
    out_departure_at: datetime
    return_departure_at: datetime
    stay_days: int
    out_airline: str
    return_airline: str
    out_flight_number: str
    return_flight_number: str
    out_price_twd: float
    return_price_twd: float
    total_price_twd: float
    out_deep_link: str
    return_deep_link: str
    fetched_at: datetime


@router.get("", response_model=list[RoundTripOut])
def list_round_trips(
    origin: Optional[str] = Query(None),
    destination: Optional[str] = Query(None),
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
) -> list[RoundTrip]:
    stmt = select(RoundTrip)
    if origin:
        stmt = stmt.where(RoundTrip.origin == origin)
    if destination:
        stmt = stmt.where(RoundTrip.destination == destination)
    stmt = stmt.order_by(RoundTrip.total_price_twd.asc()).limit(limit)
    return list(db.execute(stmt).scalars())
