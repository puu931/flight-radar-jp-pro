from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from sqlalchemy import delete

from .config import AppConfig, Route, get_config
from .db import session_scope
from .filters import passes_filters
from .models import Flight, PriceHistory
from .notifier import send_alert, send_round_trip_alert
from .round_trips import build_round_trips, top_cheapest
from .sources.aggregator import Aggregator
from .sources.base import FlightOffer

log = logging.getLogger(__name__)


def _persist_offers(offers: list[FlightOffer]) -> None:
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
) -> list[FlightOffer]:
    today = date.today()
    found: list[FlightOffer] = []
    for offset in range(1, days + 1):
        dep_date = today + timedelta(days=offset)
        offers = aggregator.search(origin, destination, dep_date)
        kept = [o for o in offers if passes_filters(o, cfg)]
        found.extend(kept)
    return found


def scan_all(notify: bool = True) -> dict:
    cfg = get_config()
    aggregator = Aggregator()
    summary: dict = {
        "routes": [],
        "alerts_sent": 0,
        "total_offers": 0,
        "round_trips": 0,
        "round_trip_alerts_sent": 0,
    }

    all_offers: list[FlightOffer] = []
    is_round_trip = cfg.trip.type == "round_trip"

    for route in cfg.routes:
        out_offers = _scan_route_direction(
            aggregator, cfg, route.origin, route.destination, cfg.search.future_days,
        )
        all_offers.extend(out_offers)

        in_offers: list[FlightOffer] = []
        if is_round_trip:
            in_offers = _scan_route_direction(
                aggregator, cfg, route.destination, route.origin, cfg.search.future_days,
            )
            all_offers.extend(in_offers)

        # Commit per route so a kill/timeout mid-scan doesn't lose hours of work.
        route_offers = out_offers + in_offers
        _persist_offers(route_offers)
        _record_price_history(route_offers)

        # One-way alerts only fire when not in round-trip mode (avoids duplicate noise).
        sent = 0
        single_alerts: list[FlightOffer] = []
        if not is_round_trip:
            single_alerts = [o for o in out_offers if o.price_twd <= route.max_price]
            single_alerts = _cheapest_per_day_airline(single_alerts)
            if notify:
                for o in single_alerts:
                    if send_alert(o):
                        sent += 1

        summary["routes"].append({
            "route": f"{route.origin}-{route.destination}",
            "out_offers": len(out_offers),
            "in_offers": len(in_offers),
            "single_leg_alerts_sent": sent,
        })
        summary["alerts_sent"] += sent

    summary["total_offers"] = len(all_offers)

    # Round-trip pairing + top-N alerts
    if is_round_trip:
        build_round_trips(cfg)
        top = top_cheapest(cfg.trip.top_n_alerts)
        summary["round_trips"] = len(top)
        sent_rt = 0
        if notify:
            for rt in top:
                if send_round_trip_alert(rt):
                    sent_rt += 1
        summary["round_trip_alerts_sent"] = sent_rt

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
