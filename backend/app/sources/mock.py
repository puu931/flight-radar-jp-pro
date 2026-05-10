from __future__ import annotations

import hashlib
import random
from datetime import date, datetime, time, timedelta

from .base import FlightOffer, FlightSource


# Rough realistic price floors (TWD) for TPE → JP economy round-trip-ish one-way slice.
_BASE_PRICE = {
    "NRT": 7800,
    "HND": 8500,
    "KIX": 7200,
    "FUK": 6400,
    "OKA": 5500,
}

_AIRLINES = [
    ("BR", "EVA Air"),
    ("JX", "Starlux"),
    ("CI", "China Airlines"),
]

_DEP_HOURS = [8, 10, 13, 15, 18, 20]


def _seeded_random(*parts: str) -> random.Random:
    digest = hashlib.sha1("|".join(parts).encode()).hexdigest()
    return random.Random(int(digest[:8], 16))


class MockSource(FlightSource):
    name = "mock"

    def search(
        self,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> list[FlightOffer]:
        rng = _seeded_random(origin, destination, departure_date.isoformat())
        base = _BASE_PRICE.get(destination, 8000)
        # Day-of-week and seasonal modulation for realism.
        weekend_boost = 1.18 if departure_date.weekday() >= 5 else 1.0
        peak_months = {1, 4, 7, 8, 12}
        season_boost = 1.25 if departure_date.month in peak_months else 1.0
        offers: list[FlightOffer] = []
        n_flights = rng.randint(2, 4)
        used_hours: set[int] = set()
        for _ in range(n_flights):
            airline_code, _ = rng.choice(_AIRLINES)
            dep_h = rng.choice([h for h in _DEP_HOURS if h not in used_hours] or _DEP_HOURS)
            used_hours.add(dep_h)
            dep_m = rng.choice([0, 15, 30, 45])
            dep_dt = datetime.combine(departure_date, time(dep_h, dep_m))
            duration = rng.choice([155, 175, 195, 220])  # mins
            arr_dt = dep_dt + timedelta(minutes=duration)
            jitter = rng.uniform(0.85, 1.4)
            price = round(base * weekend_boost * season_boost * jitter, 0)
            offers.append(FlightOffer(
                source=self.name,
                airline=airline_code,
                flight_number=f"{airline_code}{rng.randint(100, 899)}",
                origin=origin,
                destination=destination,
                departure_at=dep_dt,
                arrival_at=arr_dt,
                duration_minutes=duration,
                stops=0,
                price_twd=float(price),
                currency="TWD",
                baggage_included=rng.random() > 0.25,
                fare_class="economy" if rng.random() > 0.15 else "basic",
                deep_link=f"https://example.com/book?o={origin}&d={destination}&date={departure_date.isoformat()}",
            ))
        return offers
