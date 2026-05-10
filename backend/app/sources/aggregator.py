from __future__ import annotations

import logging
from datetime import date

from ..config import get_env
from .base import FlightOffer, FlightSource
from .mock import MockSource

log = logging.getLogger(__name__)


def _build_sources() -> list[FlightSource]:
    env = get_env()
    sources: list[FlightSource] = []
    for name in env.sources:
        try:
            if name == "mock":
                sources.append(MockSource())
            elif name == "amadeus":
                from .amadeus import AmadeusSource
                sources.append(AmadeusSource())
            else:
                log.warning("Unknown flight source %r — skipping", name)
        except Exception as e:
            log.warning("Failed to init source %s: %s", name, e)
    if not sources:
        log.warning("No flight sources configured — falling back to mock")
        sources.append(MockSource())
    return sources


class Aggregator:
    def __init__(self, sources: list[FlightSource] | None = None) -> None:
        self.sources = sources or _build_sources()

    def search(
        self,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        for src in self.sources:
            try:
                offers.extend(src.search(origin, destination, departure_date))
            except Exception as e:  # pragma: no cover
                log.exception("Source %s failed: %s", src.name, e)
        return offers
