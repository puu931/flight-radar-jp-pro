from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from sqlalchemy import delete

from .config import AppConfig, Route, get_config, route_is_active
from .db import session_scope
from .filters import passes_filters
from .models import Flight, PriceHistory
from .notifier import send_alert, send_round_trip_alert
from .round_trips import (
    below_price_for_route,
    build_round_trips,
    cheapest_for_route,
    top_cheapest_for_routes,
)
from .sources.aggregator import Aggregator
from .sources.base import FlightOffer

log = logging.getLogger(__name__)


class ScanHealthError(RuntimeError):
    """The scan ran, but did not produce data safe enough to notify from."""


def notifications_are_safe(requested: bool, sources: list[str]) -> bool:
    return requested and "mock" not in sources


def _persist_offers(offers: list[FlightOffer], *, fetched_at: datetime) -> None:
    if not offers:
        return
    with session_scope() as db:
        keys = {(o.origin, o.destination, o.departure_at.date()) for o in offers}
        for origin, destination, dep_date in keys:
            db.execute(
                delete(Flight)
                .where(Flight.origin == origin)
                .where(Flight.destination == destination)
                .where(Flight.departure_at >= datetime.combine(dep_date, datetime.min.time()))
                .where(Flight.departure_at < datetime.combine(dep_date + timedelta(days=1), datetime.min.time()))
            )
        for o in offers:
            db.add(Flight(
                source=o.source,
                airline=o.airline,
                flight_number=o.flight_number,
                origin=o.origin,
                destination=o.destination,
                departure_at=o.departure_at,
                arrival_at=o.arrival_at,
                duration_minutes=o.duration_minutes,
                stops=o.stops,
                price_twd=o.price_twd,
                currency=o.currency,
                baggage_included=o.baggage_included,
                fare_class=o.fare_class,
                deep_link=o.deep_link,
                fetched_at=fetched_at,
            ))


def _record_price_history(offers: list[FlightOffer]) -> None:
    if not offers:
        return
    by_key: dict[tuple[str, str, str, str], float] = {}
    for o in offers:
        key = (o.origin, o.destination, o.departure_at.date().isoformat(), o.airline)
        by_key[key] = min(by_key.get(key, o.price_twd), o.price_twd)
    with session_scope() as db:
        for (origin, dest, dep_date, airline), price in by_key.items():
            db.add(PriceHistory(
                origin=origin,
                destination=dest,
                departure_date=dep_date,
                airline=airline,
                min_price_twd=price,
            ))


def _scan_route_direction(
    aggregator: Aggregator,
    cfg: AppConfig,
    origin: str,
    destination: str,
    days: int,
    start_date: date | None = None,
    end_date: date | None = None,
    airlines: list[str] | None = None,
    exact_dates: bool = False,
) -> list[FlightOffer]:
    today = date.today()
    found: list[FlightOffer] = []
    first = start_date or today + timedelta(days=1)
    last = end_date or today + timedelta(days=days)
    if last < first:
        return found
    for offset in range((last - first).days + 1):
        dep_date = first + timedelta(days=offset)
        if dep_date <= today:
            continue
        offers = aggregator.search(
            origin, destination, dep_date, exact_date=exact_dates,
        )
        kept = [o for o in offers if passes_filters(o, cfg, airlines)]
        found.extend(kept)
    return found


def scan_all(notify: bool = True, *, today: date | None = None) -> dict:
    scan_started_at = datetime.utcnow()
    scan_date = today or date.today()
    cfg = get_config()
    aggregator = Aggregator()
    # Mock fares are synthetic and must never reach a real notification channel.
    notifications_enabled = notifications_are_safe(
        notify, [source.name for source in aggregator.sources],
    )
    summary: dict = {
        "routes": [],
        "alerts_sent": 0,
        "total_offers": 0,
        "round_trips": 0,
        "round_trip_alerts_sent": 0,
    }

    all_offers: list[FlightOffer] = []
    pending_single_alerts: list[FlightOffer] = []
    is_round_trip = cfg.trip.type == "round_trip"

    for route in cfg.routes:
        active = route_is_active(route, scan_date)
        if not active:
            summary["routes"].append({
                "route": f"{route.origin}-{route.destination}",
                "active": False,
                "skip_reason": "departure_window_expired",
                "out_offers": 0,
                "in_offers": 0,
                "single_leg_alerts_sent": 0,
            })
            continue
        departure_start = date.fromisoformat(route.departure_start) if route.departure_start else None
        departure_end = date.fromisoformat(route.departure_end) if route.departure_end else None
        stay_days = route.stay_days or cfg.trip.stay_days
        out_offers = _scan_route_direction(
            aggregator, cfg, route.origin, route.destination, cfg.search.future_days,
            departure_start, departure_end, route.airlines,
            bool(departure_start or departure_end),
        )
        all_offers.extend(out_offers)

        in_offers: list[FlightOffer] = []
        if is_round_trip:
            in_offers = _scan_route_direction(
                aggregator, cfg, route.destination, route.origin, cfg.search.future_days,
                (departure_start + timedelta(days=min(stay_days))) if departure_start else None,
                (departure_end + timedelta(days=max(stay_days))) if departure_end else None,
                route.airlines,
                bool(departure_start or departure_end),
            )
            all_offers.extend(in_offers)

        # Commit per route so a kill/timeout mid-scan doesn't lose hours of work.
        route_offers = out_offers + in_offers
        _persist_offers(route_offers, fetched_at=scan_started_at)
        _record_price_history(route_offers)

        # One-way alerts only fire when not in round-trip mode (avoids duplicate noise).
        sent = 0
        single_alerts: list[FlightOffer] = []
        if not is_round_trip:
            single_alerts = [o for o in out_offers if o.price_twd <= route.max_price]
            single_alerts = _cheapest_per_day_airline(single_alerts)
            pending_single_alerts.extend(single_alerts)

        summary["routes"].append({
            "route": f"{route.origin}-{route.destination}",
            "active": True,
            "skip_reason": None,
            "out_offers": len(out_offers),
            "in_offers": len(in_offers),
            "single_leg_alerts_sent": sent,
        })
        summary["alerts_sent"] += sent

    summary["total_offers"] = len(all_offers)
    active_routes = [route for route in cfg.routes if route_is_active(route, scan_date)]
    if active_routes and summary["total_offers"] <= 0:
        raise ScanHealthError("scan returned no flight offers")

    for route, route_summary in zip(cfg.routes, summary["routes"]):
        required = route_summary["active"] and bool(
            route.departure_start or route.departure_end
            or route.alert_below or route.top_n_alerts
        )
        if required and (
            route_summary["out_offers"] <= 0
            or (is_round_trip and route_summary["in_offers"] <= 0)
        ):
            raise ScanHealthError(
                f"required route {route.origin}-{route.destination} "
                "returned no data on one or more legs"
            )

    # Round-trip pairing + top-N alerts
    if is_round_trip:
        round_trips = build_round_trips(
            cfg, fetched_at=scan_started_at, today=scan_date,
        )
        summary["round_trips"] = len(round_trips)
        routes_with_combos = {
            (round_trip.origin, round_trip.destination)
            for round_trip in round_trips
        }
        for route in cfg.routes:
            required = route_is_active(route, scan_date) and bool(
                route.departure_start or route.departure_end
                or route.alert_below or route.top_n_alerts
            )
            if required and (route.origin, route.destination) not in routes_with_combos:
                raise ScanHealthError(
                    f"required route {route.origin}-{route.destination} "
                    "produced no round-trip combinations"
                )
        sent_rt = 0
        if notifications_enabled:
            legacy_routes: list[tuple[str, str]] = []
            for route in cfg.routes:
                if not route_is_active(route, scan_date):
                    continue
                if route.alert_below or route.top_n_alerts:
                    cheap = below_price_for_route(
                        route.origin, route.destination, route.alert_below,
                    ) if route.alert_below else []
                    top = cheapest_for_route(
                        route.origin, route.destination, route.top_n_alerts,
                    ) if route.top_n_alerts else []
                    cheap_fps = {rt.fingerprint for rt in cheap}
                    for rt in cheap:
                        if send_round_trip_alert(rt):
                            sent_rt += 1
                    for rt in top:
                        if rt.fingerprint not in cheap_fps and send_round_trip_alert(rt, only_if_new=True):
                            sent_rt += 1
                else:
                    legacy_routes.append((route.origin, route.destination))
            # Preserve the original behavior: one global top-N shared by all
            # routes that do not opt into route-specific monitoring.
            for rt in top_cheapest_for_routes(legacy_routes, cfg.trip.top_n_alerts):
                if send_round_trip_alert(rt):
                    sent_rt += 1
        summary["round_trip_alerts_sent"] = sent_rt
    elif notifications_enabled:
        for offer in pending_single_alerts:
            if send_alert(offer):
                summary["alerts_sent"] += 1

    log.info("Scan complete: %s", summary)
    return summary


def _cheapest_per_day_airline(offers: list[FlightOffer]) -> list[FlightOffer]:
    best: dict[tuple[str, str, str, str], FlightOffer] = {}
    for o in offers:
        k = (o.origin, o.destination, o.departure_at.date().isoformat(), o.airline)
        cur = best.get(k)
        if cur is None or o.price_twd < cur.price_twd:
            best[k] = o
    return list(best.values())
