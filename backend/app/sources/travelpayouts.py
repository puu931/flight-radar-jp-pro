from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

import httpx

from ..config import get_env
from .base import FlightOffer, FlightSource

log = logging.getLogger(__name__)

API_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"


class TravelpayoutsSource(FlightSource):
    """Travelpayouts (Aviasales) flight prices.

    Docs: https://support.travelpayouts.com/hc/en-us/articles/203956083
    Free, affiliate-based. Booking links carry your marker so completed
    bookings earn commission.

    Note: prices are cached on Travelpayouts' side (minutes-to-hours delay),
    and baggage information is not exposed by the API. We mark
    `baggage_included=False` to be honest — set `baggage_required: false`
    in config.yaml to keep these results.
    """

    name = "travelpayouts"

    def __init__(self) -> None:
        env = get_env()
        if not env.travelpayouts_token:
            raise RuntimeError("TRAVELPAYOUTS_TOKEN not set")
        self.token = env.travelpayouts_token
        self.marker = env.travelpayouts_marker
        # Cache per (origin, destination, year-month) → offers.
        # Lives for the lifetime of the Aggregator instance (one scan run),
        # which lets a 90-day daily loop hit the API only ~3 times per route.
        self._cache: dict[tuple[str, str, str], list[FlightOffer]] = {}

    def search(
        self,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> list[FlightOffer]:
        ym = departure_date.strftime("%Y-%m")
        key = (origin, destination, ym)
        if key not in self._cache:
            self._cache[key] = self._fetch_month(origin, destination, ym)
        return [
            o for o in self._cache[key]
            if o.departure_at.date() == departure_date
        ]

    @staticmethod
    def _canonicalize_endpoint(req: str, response: str) -> str:
        """Travelpayouts normalises NRT/HND → TYO, KIX/ITM → OSA, etc.
        Keep the airport code the caller asked for so results bucket per-route correctly.
        """
        req = req.upper()
        response = response.upper()
        city_to_airports = {
            "TYO": {"NRT", "HND"},
            "OSA": {"KIX", "ITM"},
            "TPE": {"TPE", "TSA"},
        }
        if response in city_to_airports and req in city_to_airports[response]:
            return req
        return response or req

    def _fetch_month(self, origin: str, destination: str, ym: str) -> list[FlightOffer]:
        # Pass token via header (X-Access-Token) instead of query string so it
        # doesn't end up in httpx's "HTTP Request: GET <url>" log lines.
        params = {
            "origin": origin,
            "destination": destination,
            "departure_at": ym,
            "currency": "twd",
            "direct": "true",
            "one_way": "true",
            "limit": 1000,
            "sorting": "price",
        }
        headers = {"X-Access-Token": self.token}
        try:
            r = httpx.get(API_URL, params=params, headers=headers, timeout=15)
            r.raise_for_status()
            data = r.json().get("data") or []
        except Exception as e:
            log.warning("Travelpayouts fetch failed for %s→%s %s: %s",
                        origin, destination, ym, e)
            return []
        offers: list[FlightOffer] = []
        for d in data:
            o = self._parse(d, origin, destination)
            if o is not None:
                offers.append(o)
        log.info("Travelpayouts %s→%s %s: %d offers", origin, destination, ym, len(offers))
        return offers

    def _parse(
        self,
        d: dict[str, Any],
        req_origin: str,
        req_destination: str,
    ) -> Optional[FlightOffer]:
        try:
            airline = str(d["airline"]).upper()
            flight_no_raw = str(d.get("flight_number") or "").strip()
            flight_number = f"{airline}{flight_no_raw}" if flight_no_raw else airline
            dep = datetime.fromisoformat(str(d["departure_at"]))
            duration = int(d.get("duration") or 0)
            arr = dep + timedelta(minutes=duration)
            link = str(d.get("link") or "")
            if link.startswith("/"):
                link = "https://www.aviasales.com" + link
            if link and self.marker:
                sep = "&" if "?" in link else "?"
                link = f"{link}{sep}marker={self.marker}"
            origin_resp = str(d.get("origin") or "").upper()
            dest_resp = str(d.get("destination") or "").upper()
            return FlightOffer(
                source=self.name,
                airline=airline,
                flight_number=flight_number,
                origin=self._canonicalize_endpoint(req_origin, origin_resp),
                destination=self._canonicalize_endpoint(req_destination, dest_resp),
                # Strip tz to keep parity with the rest of the codebase.
                departure_at=dep.replace(tzinfo=None),
                arrival_at=arr.replace(tzinfo=None),
                duration_minutes=duration,
                stops=int(d.get("transfers") or 0),
                price_twd=float(d["price"]),
                currency="TWD",
                baggage_included=False,
                fare_class="economy",
                deep_link=link,
            )
        except (KeyError, ValueError, TypeError) as e:
            log.debug("Skipping malformed Travelpayouts row: %s", e)
            return None
