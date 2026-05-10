from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_config
from ..db import get_db
from ..models import Flight
from ..scanner import scan_all
from ..schemas import FlightOut

router = APIRouter()


@router.get("", response_model=list[FlightOut])
def list_flights(
    origin: Optional[str] = Query(None),
    destination: Optional[str] = Query(None),
    airline: Optional[str] = Query(None),
    max_price: Optional[float] = Query(None),
    limit: int = Query(200, le=1000),
    db: Session = Depends(get_db),
) -> list[Flight]:
    stmt = select(Flight)
    if origin:
        stmt = stmt.where(Flight.origin == origin)
    if destination:
        stmt = stmt.where(Flight.destination == destination)
    if airline:
        stmt = stmt.where(Flight.airline == airline)
    if max_price is not None:
        stmt = stmt.where(Flight.price_twd <= max_price)
    stmt = stmt.order_by(Flight.price_twd.asc()).limit(limit)
    return list(db.execute(stmt).scalars())


@router.get("/cheapest", response_model=list[FlightOut])
def cheapest(
    limit: int = Query(10, le=100),
    db: Session = Depends(get_db),
) -> list[Flight]:
    cfg = get_config()
    stmt = (
        select(Flight)
        .where(Flight.airline.in_(cfg.airlines))
        .order_by(Flight.price_twd.asc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars())


@router.post("/scan")
def trigger_scan(notify: bool = Query(False)) -> dict:
    """Manually trigger a scan. Returns the per-route summary."""
    return scan_all(notify=notify)
