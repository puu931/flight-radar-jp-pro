from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import delete

from .config import AppConfig, Route, get_config
from .db import session_scope
from .filters import passes_filters
from .models import Flight, PriceHistory
from .notifier import send_alert
from .sources.aggregator import Aggregator
from .sources.base import FlightOffer

log = logging.getLogger(__name__)


def _persist_offers(offers: list[FlightOffer]) -> None:
    if not offers:
        return
    with session_scope() as db:
        # Reset flights for the (origin, destination, departure_date) keys we just refreshed
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
    # Aggregate min price per (origin, dest, dep_date, airline)
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


def scan_route(
    aggregator: Aggregator,
    cfg: AppConfig,
    route: Route,
    days: int,
) -> list[FlightOffer]:
    today = date.today()
    found: list[FlightOffer] = []
    for offset in range(1, days + 1):
        dep_date = today + timedelta(days=offset)
        offers = aggregator.search(route.origin, route.destination, dep_date)
        # Apply whitelist + filters
        kept = [o for o in offers if passes_filters(o, cfg)]
        found.extend(kept)
    return found


def scan_all(notify: bool = True) -> dict:
    cfg = get_config()
    aggregator = Aggregator()
    summary: dict = {"routes": [], "alerts_sent": 0, "total_offers": 0}

    all_offers: list[FlightOffer] = []
    for route in cfg.routes:
        offers = scan_route(aggregator, cfg, route, cfg.search.future_days)
        all_offers.extend(offers)

        # alerts: any offer ≤ max_price triggers
        alerts = [o for o in offers if o.price_twd <= route.max_price]
        # cheapest per (date, airline) only — reduce noise
        deduped_alerts = _cheapest_per_day_airline(alerts)

        sent = 0
        if notify:
            for o in deduped_alerts:
                if send_alert(o):
                    sent += 1
        summary["routes"].append({
            "route": f"{route.origin}-{route.destination}",
            "offers": len(offers),
            "alerts": len(deduped_alerts),
            "alerts_sent": sent,
        })
        summary["alerts_sent"] += sent

    summary["total_offers"] = len(all_offers)
    _persist_offers(all_offers)
    _record_price_history(all_offers)
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
