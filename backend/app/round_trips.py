from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Iterable

from sqlalchemy import delete, select

from .config import AppConfig, Route, route_is_active
from .db import session_scope
from .models import Flight, RoundTrip, RoundTripHistory

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
    max_total: float | None,
) -> list[dict]:
    """Pair outbound + return flights by allowed stay length, keep unique results."""
    in_by_date: dict = defaultdict(list)
    for f in in_flights:
        in_by_date[f.departure_at.date()].append(f)
    combos: list[dict] = []
    # Historical scans can contain the same fare more than once. RoundTrip uses
    # this fingerprint as a unique key, so discard duplicate combinations before
    # they reach the database (and before history sample counts are recorded).
    seen_fingerprints: set[str] = set()
    for out in out_flights:
        out_date = out.departure_at.date()
        for stay in stay_days:
            ret_date = out_date + timedelta(days=stay)
            for ret in in_by_date.get(ret_date, []):
                total = float(out.price_twd) + float(ret.price_twd)
                if max_total is not None and total > max_total:
                    continue
                persisted_fingerprint = _round_trip_fp(out, ret)
                if persisted_fingerprint in seen_fingerprints:
                    continue
                seen_fingerprints.add(persisted_fingerprint)
                combos.append({
                    "out": out,
                    "ret": ret,
                    "stay": stay,
                    "total": total,
                })
    return combos


def build_round_trips(
    cfg: AppConfig,
    *,
    fetched_at: datetime,
    today: date | None = None,
) -> list[RoundTrip]:
    """Generate round trips from rows fetched by the current scan only.

    Wipes existing round_trips table before writing fresh combinations.
    Returns the persisted RoundTrip rows (already committed).
    """
    out_records: list[RoundTrip] = []
    with session_scope() as db:
        # Reset
        db.execute(delete(RoundTrip))

        scan_date = today or date.today()
        for route in cfg.routes:
            if not route_is_active(route, scan_date):
                log.info(
                    "RoundTrip %s↔%s: skipped expired departure window ending %s",
                    route.origin, route.destination, route.departure_end,
                )
                continue
            departure_start = (
                datetime.fromisoformat(route.departure_start).date()
                if route.departure_start else None
            )
            departure_end = (
                datetime.fromisoformat(route.departure_end).date()
                if route.departure_end else None
            )
            out_flights = list(db.execute(
                select(Flight)
                .where(Flight.origin == route.origin)
                .where(Flight.destination == route.destination)
                .where(Flight.fetched_at == fetched_at)
            ).scalars())
            in_flights = list(db.execute(
                select(Flight)
                .where(Flight.origin == route.destination)
                .where(Flight.destination == route.origin)
                .where(Flight.fetched_at == fetched_at)
            ).scalars())
            if route.airlines:
                out_flights = [f for f in out_flights if f.airline in route.airlines]
                in_flights = [f for f in in_flights if f.airline in route.airlines]
            if departure_start:
                out_flights = [f for f in out_flights if f.departure_at.date() >= departure_start]
            if departure_end:
                out_flights = [f for f in out_flights if f.departure_at.date() <= departure_end]
            if not out_flights or not in_flights:
                log.info("RoundTrip %s↔%s: no data on one leg (out=%d, in=%d)",
                         route.origin, route.destination, len(out_flights), len(in_flights))
                continue
            # A dated fare watch needs the actual top-N even when it is above the
            # deal threshold, so it deliberately has no pairing price ceiling.
            max_total = None if (route.alert_below or route.top_n_alerts) else float(
                route.max_round_trip or route.max_price * 2
            )
            stay_days = route.stay_days or cfg.trip.stay_days
            combos = pair_route(out_flights, in_flights, stay_days, max_total)
            log.info("RoundTrip %s↔%s: out=%d in=%d → %d combos under %s",
                     route.origin, route.destination,
                     len(out_flights), len(in_flights), len(combos),
                     "none" if max_total is None else int(max_total))

            # Append a history row so trends can chart min round-trip price per scan.
            if combos:
                min_total = min(c["total"] for c in combos)
                db.add(RoundTripHistory(
                    origin=route.origin,
                    destination=route.destination,
                    min_total_twd=min_total,
                    sample_count=len(combos),
                ))

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
        # Keep the returned records readable after session_scope commits so the
        # caller can validate per-route coverage before sending notifications.
        db.flush()
        for record in out_records:
            db.expunge(record)
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


def top_cheapest_for_routes(routes: list[tuple[str, str]], limit: int) -> list[RoundTrip]:
    """Global top-N across a selected set of legacy routes."""
    if not routes or limit <= 0:
        return []
    allowed = set(routes)
    with session_scope() as db:
        candidates = list(db.execute(
            select(RoundTrip).order_by(RoundTrip.total_price_twd.asc())
        ).scalars())
        rows = select_top_for_routes(candidates, allowed, limit)
        for row in rows:
            db.expunge(row)
        return rows


def select_top_for_routes(
    candidates: list[RoundTrip],
    allowed: set[tuple[str, str]],
    limit: int,
) -> list[RoundTrip]:
    """Select one global top-N from already price-ordered candidates."""
    return [r for r in candidates if (r.origin, r.destination) in allowed][:limit]


def cheapest_for_route(origin: str, destination: str, limit: int) -> list[RoundTrip]:
    """Return detached cheapest combinations for one configured route."""
    with session_scope() as db:
        rows = list(db.execute(
            select(RoundTrip)
            .where(RoundTrip.origin == origin)
            .where(RoundTrip.destination == destination)
            .order_by(RoundTrip.total_price_twd.asc())
            .limit(limit)
        ).scalars())
        for row in rows:
            db.expunge(row)
        return rows


def below_price_for_route(origin: str, destination: str, price: float) -> list[RoundTrip]:
    """Return detached combinations below a route's deal threshold."""
    with session_scope() as db:
        rows = list(db.execute(
            select(RoundTrip)
            .where(RoundTrip.origin == origin)
            .where(RoundTrip.destination == destination)
            .where(RoundTrip.total_price_twd < price)
            .order_by(RoundTrip.total_price_twd.asc())
        ).scalars())
        for row in rows:
            db.expunge(row)
        return rows
