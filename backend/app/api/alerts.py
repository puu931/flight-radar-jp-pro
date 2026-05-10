from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AlertLog
from ..schemas import AlertOut

router = APIRouter()


@router.get("", response_model=list[AlertOut])
def list_alerts(
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
) -> list[AlertLog]:
    stmt = select(AlertLog).order_by(AlertLog.sent_at.desc()).limit(limit)
    return list(db.execute(stmt).scalars())
