from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class FlightOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    airline: str
    flight_number: str
    origin: str
    destination: str
    departure_at: datetime
    arrival_at: datetime
    duration_minutes: int
    stops: int
    price_twd: float
    currency: str
    baggage_included: bool
    fare_class: str
    deep_link: str
    fetched_at: datetime


class CalendarCell(BaseModel):
    date: str          # YYYY-MM-DD
    min_price_twd: float
    flight_count: int
    airline: Optional[str] = None


class TrendPoint(BaseModel):
    recorded_at: datetime
    min_price_twd: float


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    origin: str
    destination: str
    airline: str
    flight_number: str
    departure_at: datetime
    price_twd: float
    sent_at: datetime
    delivered: bool
    message: str


class RouteIn(BaseModel):
    origin: str
    destination: str
    max_price: int


class SettingsOut(BaseModel):
    airlines: list[str]
    routes: list[RouteIn]
    filters: dict[str, Any]
    search: dict[str, Any]
    notification: dict[str, Any]
