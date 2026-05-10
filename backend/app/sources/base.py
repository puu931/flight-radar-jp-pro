from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class FlightOffer:
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
    currency: str = "TWD"
    baggage_included: bool = False
    fare_class: str = "economy"
    deep_link: str = ""


class FlightSource(ABC):
    name: str = "base"

    @abstractmethod
    def search(
        self,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> list[FlightOffer]:
        ...
