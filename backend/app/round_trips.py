from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Iterable

from sqlalchemy import delete, select

from .config import AppConfig, Route
from .db import session_scope
from .models import Flight, RoundTrip

log = logging.getLogger(__name__)


def _round_trip_fp(out: Flight, ret: Flight) -> str:
    key = (
        f"{out.origin}|{out.destination}|"
        f"{out.airline}{out.flight_number}|{out.departure_at.isoformat()}|{int(out.price_twd)}"
        f"||{ret.airline}{ret.flight_number}|{ret.departure_at.isoformat()}|{int(ret.price_twd)}"
    )
    return hashlib.sha1(key.encode()).hexdigest()


def pair_route(
    out_flights: list[Flight],
    in_flights: list[Flight],
    stay_days: list[int],
    max_total: float,
) -> list[dict]:
    """Pair outbound + return flights by allowed stay length, keep ones under max_total."""
    in_by_date: dict = defaultdict(list)
    for f in in_flights:
        in_by_date[f.departure_at.date()].append(f)
    combos: list[dict] = []
    for out in out_flights:
        out_date = out.departure_at.date()
        for stay in stay_days:
            ret_date = out_date + timedelta(days=stay)
            for ret in in_by_date.get(ret_date, []):
                total = float(out.price_twd) + float(ret.price_twd)
                if total > max_total:
                    continue
                combos.append({
                    "out": out,
                    "ret": ret,
                    "stay": stay,
                    "total": total,
                })
    return combos


def build_round_trips(cfg: AppConfig) -> list[RoundTrip]:
    """Generate round-trip records from flights currently in the DB.

    Wipes existing round_trips table before writing fresh combinations.
    Returns the persisted RoundTrip rows (already committed).
    """
    out_records: list[RoundTrip] = []
    with session_scope() as db:
        # Reset
        db.execute(delete(RoundTrip))

        for route in cfg.routes:
            out_flights = list(db.execute(
                select(Flight)
                .where(Flight.origin == route.origin)
                .where(Flight.destination == route.destination)
            ).scalars())
            in_flights = list(db.execute(
                select(Flight)
                .where(Flight.origin == route.destination)
                .where(Flight.destination == route.origin)
            ).scalars())
            if not out_flights or not in_flights:
                log.info("RoundTrip %s↔%s: no data on one leg (out=%d, in=%d)",
                         route.origin, route.destination, len(out_flights), len(in_flights))
                continue
            max_total = float(route.max_round_trip or route.max_price * 2)
            combos = pair_route(out_flights, in_flights, cfg.trip.stay_days, max_total)
            log.info("RoundTrip %s↔%s: out=%d in=%d → %d combos under %s",
                     route.origin, route.destination,
                     len(out_flights), len(in_flights), len(combos), int(max_total))

            for c in combos:
                out, ret = c["out"], c["ret"]
                rt = RoundTrip(
                    fingerprint=_round_trip_fp(out, ret),
                    origin=route.origin,
                    destination=route.destination,
                    out_departure_at=out.departure_at,
                    return_departure_at=ret.departure_at,
                    stay_days=c["stay"],
                    out_airline=out.airline,
                    return_airline=ret.airline,
                    out_flight_number=out.flight_number,
                    return_flight_number=ret.flight_number,
                    out_price_twd=float(out.price_twd),
                    return_price_twd=float(ret.price_twd),
                    total_price_twd=c["total"],
                    out_deep_link=out.deep_link,
                    return_deep_link=ret.deep_link,
                )
                db.add(rt)
                out_records.append(rt)
    return out_records


def top_cheapest(limit: int = 5) -> list[RoundTrip]:
    with session_scope() as db:
        rows = list(db.execute(
            select(RoundTrip)
            .order_by(RoundTrip.total_price_twd.asc())
            .limit(limit)
        ).scalars())
        # detach so callers don't see DetachedInstance errors
        for r in rows:
            db.expunge(r)
        return rows
