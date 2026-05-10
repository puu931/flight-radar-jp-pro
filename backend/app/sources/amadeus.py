from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from ..config import get_env
from .base import FlightOffer, FlightSource

log = logging.getLogger(__name__)


class AmadeusSource(FlightSource):
    """Amadeus Self-Service: Flight Offers Search.

    Docs: https://developers.amadeus.com/self-service/category/flights
    Free tier: 2000 calls/month. Test environment uses test data; switch
    to production by changing the hostname.
    """

    name = "amadeus"

    def __init__(self) -> None:
        env = get_env()
        if not env.amadeus_api_key or not env.amadeus_api_secret:
            raise RuntimeError("AMADEUS_API_KEY / AMADEUS_API_SECRET not set")
        # Lazy import so the package is only required when this source is used.
        from amadeus import Client
        self.client = Client(
            client_id=env.amadeus_api_key,
            client_secret=env.amadeus_api_secret,
        )
        self._fx = env

    def search(
        self,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> list[FlightOffer]:
        try:
            response = self.client.shopping.flight_offers_search.get(
                originLocationCode=origin,
                destinationLocationCode=destination,
                departureDate=departure_date.isoformat(),
                adults=1,
                currencyCode="TWD",
                nonStop="true",
                max=20,
            )
        except Exception as e:  # pragma: no cover - network
            log.warning("Amadeus search failed for %s→%s on %s: %s",
                        origin, destination, departure_date, e)
            return []

        return [self._parse(o) for o in (response.data or []) if self._parse(o)]

    def _parse(self, offer: dict[str, Any]) -> FlightOffer | None:
        try:
            itin = offer["itineraries"][0]
            segments = itin["segments"]
            if len(segments) != 1:
                return None  # not a direct flight
            seg = segments[0]
            airline = seg["carrierCode"]
            flight_number = f"{airline}{seg['number']}"
            dep_dt = datetime.fromisoformat(seg["departure"]["at"])
            arr_dt = datetime.fromisoformat(seg["arrival"]["at"])
            duration = self._iso8601_to_minutes(itin.get("duration", "PT0M"))
            price_total = float(offer["price"]["grandTotal"])
            currency = offer["price"]["currency"]
            price_twd = self._to_twd(price_total, currency)
            traveler = (offer.get("travelerPricings") or [{}])[0]
            fare_segment = (traveler.get("fareDetailsBySegment") or [{}])[0]
            included_bags = fare_segment.get("includedCheckedBags", {})
            baggage_included = bool(
                included_bags.get("quantity", 0) or included_bags.get("weight", 0)
            )
            fare_class = (fare_segment.get("brandedFare") or fare_segment.get("cabin") or "economy").lower()
            return FlightOffer(
                source=self.name,
                airline=airline,
                flight_number=flight_number,
                origin=seg["departure"]["iataCode"],
                destination=seg["arrival"]["iataCode"],
                departure_at=dep_dt,
                arrival_at=arr_dt,
                duration_minutes=duration,
                stops=0,
                price_twd=round(price_twd, 0),
                currency="TWD",
                baggage_included=baggage_included,
                fare_class=fare_class,
                deep_link="",
            )
        except (KeyError, IndexError, ValueError) as e:
            log.debug("Skipping malformed Amadeus offer: %s", e)
            return None

    def _to_twd(self, amount: float, currency: str) -> float:
        currency = currency.upper()
        if currency == "TWD":
            return amount
        if currency == "USD":
            return amount * self._fx.usd_to_twd
        if currency == "JPY":
            return amount * self._fx.jpy_to_twd
        return amount  # fallback assume TWD-ish

    @staticmethod
    def _iso8601_to_minutes(s: str) -> int:
        # PT2H35M
        s = s.replace("PT", "")
        hours = 0
        minutes = 0
        if "H" in s:
            h_str, _, s = s.partition("H")
            hours = int(h_str or 0)
        if "M" in s:
            m_str, _, _ = s.partition("M")
            minutes = int(m_str or 0)
        return hours * 60 + minutes
