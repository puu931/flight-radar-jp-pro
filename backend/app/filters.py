from __future__ import annotations

from datetime import time

from .config import AppConfig
from .sources.base import FlightOffer

RED_EYE_START = time(0, 0)
RED_EYE_END = time(5, 30)


def _parse_hhmm(value: str) -> time:
    h, m = value.split(":")
    return time(int(h), int(m))


def passes_filters(offer: FlightOffer, cfg: AppConfig) -> bool:
    f = cfg.filters
    # Airline whitelist
    if cfg.airlines and offer.airline not in cfg.airlines:
        return False
    # Direct only
    if f.direct_only and offer.stops > 0:
        return False
    # Baggage
    if f.baggage_required and not offer.baggage_included:
        return False
    # Basic fare
    if f.exclude_basic_fare and offer.fare_class.lower() == "basic":
        return False
    # Red-eye
    if f.avoid_red_eye:
        dep_t = offer.departure_at.time()
        arr_t = offer.arrival_at.time()
        if RED_EYE_START <= dep_t <= RED_EYE_END or RED_EYE_START <= arr_t <= RED_EYE_END:
            return False
    # Time window
    if f.departure_after and offer.departure_at.time() < _parse_hhmm(f.departure_after):
        return False
    if f.arrival_before and offer.arrival_at.time() > _parse_hhmm(f.arrival_before):
        return False
    return True
