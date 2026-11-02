from __future__ import annotations

import os
import unittest
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

# Force every direct unittest invocation onto an isolated database before any
# app module imports create the SQLAlchemy engine. Never inherit DATABASE_URL.
os.environ["DATABASE_URL"] = f"sqlite:////tmp/flight-radar-tests-{os.getpid()}.db"
os.environ["FLIGHT_SOURCES"] = "mock"

from app.config import AppConfig, CONFIG_PATH, Route, route_is_active
from app.db import init_db, session_scope
from app.models import Flight, RoundTrip
from app.notifier import required_delivery_succeeded, round_trip_itinerary_fingerprint
from app.round_trips import build_round_trips, pair_route, select_top_for_routes
from app.scanner import ScanHealthError, notifications_are_safe, scan_all
from app.sources.aggregator import Aggregator
from app.sources.base import FlightOffer
from sqlalchemy import delete


def flight(direction: str, departure: date, price: float, airline: str = "BR") -> Flight:
    origin, destination = ("TPE", "CTS") if direction == "out" else ("CTS", "TPE")
    departure_at = datetime.combine(departure, datetime.min.time()).replace(hour=10)
    return Flight(
        source="test",
        airline=airline,
        flight_number=f"{airline}123",
        origin=origin,
        destination=destination,
        departure_at=departure_at,
        arrival_at=departure_at + timedelta(hours=4),
        duration_minutes=240,
        stops=0,
        price_twd=price,
        currency="TWD",
        baggage_included=False,
        fare_class="economy",
        deep_link="",
    )


class ExactSource:
    name = "exact-test"

    def __init__(self) -> None:
        self.sampled = 0
        self.exact = 0

    def search(self, origin: str, destination: str, departure_date: date):
        self.sampled += 1
        return []

    def search_exact(self, origin: str, destination: str, departure_date: date):
        self.exact += 1
        return []


class HokkaidoMonitorTests(unittest.TestCase):
    def test_expired_dated_route_is_inactive(self) -> None:
        route = Route(
            origin="TPE", destination="CTS", max_price=10_000,
            departure_start="2026-10-10", departure_end="2026-10-31",
        )
        self.assertFalse(route_is_active(route, date(2026, 10, 31)))
        self.assertFalse(route_is_active(route, date(2026, 11, 2)))

    def test_expired_route_is_skipped_but_remains_visible_in_summary(self) -> None:
        cfg = AppConfig.load(CONFIG_PATH)
        cfg.routes = [
            next(r for r in cfg.routes if (r.origin, r.destination) == ("TPE", "CTS"))
        ]

        class NoSearchAggregator:
            sources = [SimpleNamespace(name="mock")]

            def search(self, *_args, **_kwargs):
                raise AssertionError("expired route must not call a flight source")

        with (
            patch("app.scanner.get_config", return_value=cfg),
            patch("app.scanner.Aggregator", return_value=NoSearchAggregator()),
            patch("app.scanner.build_round_trips", return_value=[]) as build,
            patch("app.scanner.send_round_trip_alert") as notifier,
        ):
            summary = scan_all(notify=True, today=date(2026, 11, 2))

        self.assertEqual(summary["total_offers"], 0)
        self.assertEqual(summary["round_trips"], 0)
        self.assertEqual(summary["routes"], [{
            "route": "TPE-CTS",
            "active": False,
            "skip_reason": "departure_window_expired",
            "out_offers": 0,
            "in_offers": 0,
            "single_leg_alerts_sent": 0,
        }])
        build.assert_called_once()
        notifier.assert_not_called()

    def test_future_dated_route_is_active(self) -> None:
        route = Route(
            origin="TPE", destination="CTS", max_price=10_000,
            departure_start="2026-10-10", departure_end="2026-10-31",
        )
        self.assertTrue(route_is_active(route, date(2026, 10, 30)))

    def test_undated_legacy_route_remains_active(self) -> None:
        route = Route(origin="TPE", destination="NRT", max_price=10_000)
        self.assertTrue(route_is_active(route, date(2099, 1, 1)))

    def test_build_round_trips_ignores_stale_flights(self) -> None:
        init_db()
        scan_started_at = datetime.utcnow()
        departure = date(2026, 10, 15)
        stale_out = flight("out", departure, 1_000, "JX")
        stale_in = flight("in", departure + timedelta(days=5), 1_000, "BR")
        fresh_out = flight("out", departure, 12_000, "JX")
        fresh_in = flight("in", departure + timedelta(days=5), 8_000, "BR")
        stale_out.fetched_at = stale_in.fetched_at = scan_started_at - timedelta(seconds=1)
        fresh_out.fetched_at = fresh_in.fetched_at = scan_started_at
        with session_scope() as db:
            db.execute(delete(RoundTrip))
            db.execute(delete(Flight))
            db.add_all([stale_out, stale_in, fresh_out, fresh_in])

        rows = build_round_trips(
            AppConfig.load(CONFIG_PATH),
            fetched_at=scan_started_at,
            today=date(2026, 10, 14),
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].origin, rows[0].destination), ("TPE", "CTS"))
        with session_scope() as db:
            cts_rows = list(db.query(RoundTrip).filter_by(
                origin="TPE", destination="CTS",
            ))
            self.assertEqual(len(cts_rows), 1)
            self.assertEqual(cts_rows[0].total_price_twd, 20_000)

    def test_required_route_missing_leg_fails_before_notifier(self) -> None:
        class LiveSource:
            name = "live-test"

        class PartialAggregator:
            sources = [LiveSource()]

            def search(self, origin, destination, departure_date, *, exact_date=False):
                if {origin, destination} != {"TPE", "NRT"}:
                    return []
                departure_at = datetime.combine(departure_date, datetime.min.time()).replace(hour=10)
                return [FlightOffer(
                    source="test", airline="BR", flight_number="BR123",
                    origin=origin, destination=destination,
                    departure_at=departure_at,
                    arrival_at=departure_at + timedelta(hours=4),
                    duration_minutes=240, stops=0, price_twd=8_000,
                    currency="TWD", baggage_included=False,
                    fare_class="economy", deep_link="",
                )]

        with (
            patch("app.scanner.Aggregator", return_value=PartialAggregator()),
            patch("app.scanner._persist_offers"),
            patch("app.scanner._record_price_history"),
            patch("app.scanner.send_round_trip_alert") as notifier,
        ):
            with self.assertRaisesRegex(ScanHealthError, "required route TPE-CTS"):
                scan_all(notify=True, today=date(2026, 10, 14))
        notifier.assert_not_called()

    def test_empty_scan_fails_before_any_notifier(self) -> None:
        class LiveSource:
            name = "live-test"

        class EmptyAggregator:
            sources = [LiveSource()]

            def search(self, origin, destination, departure_date, *, exact_date=False):
                return []

        with (
            patch("app.scanner.Aggregator", return_value=EmptyAggregator()),
            patch("app.scanner._persist_offers"),
            patch("app.scanner._record_price_history"),
            patch("app.scanner.send_alert") as one_way_notifier,
            patch("app.scanner.send_round_trip_alert") as round_trip_notifier,
        ):
            with self.assertRaisesRegex(ScanHealthError, "no flight offers"):
                scan_all(notify=True, today=date(2026, 10, 14))
        one_way_notifier.assert_not_called()
        round_trip_notifier.assert_not_called()

    def test_required_route_without_compatible_combo_fails_before_notifier(self) -> None:
        cfg = AppConfig.load(CONFIG_PATH)
        cts = next(r for r in cfg.routes if (r.origin, r.destination) == ("TPE", "CTS"))
        departure = date(2026, 10, 15)
        out_offer = FlightOffer(
            source="test", airline="JX", flight_number="JX850",
            origin="TPE", destination="CTS",
            departure_at=datetime.combine(departure, datetime.min.time()).replace(hour=10),
            arrival_at=datetime.combine(departure, datetime.min.time()).replace(hour=14),
            duration_minutes=240, stops=0, price_twd=10_000,
        )
        # Both legs exist, but a two-day gap cannot match CTS stay_days [5, 6, 7].
        in_offer = FlightOffer(
            source="test", airline="BR", flight_number="BR115",
            origin="CTS", destination="TPE",
            departure_at=datetime.combine(departure + timedelta(days=2), datetime.min.time()).replace(hour=10),
            arrival_at=datetime.combine(departure + timedelta(days=2), datetime.min.time()).replace(hour=14),
            duration_minutes=240, stops=0, price_twd=10_000,
        )

        def scan_direction(_aggregator, _cfg, origin, destination, *_args, **_kwargs):
            if (origin, destination) == (cts.origin, cts.destination):
                return [out_offer]
            if (origin, destination) == (cts.destination, cts.origin):
                return [in_offer]
            return []

        # A legacy route having a valid combo must not mask CTS having none.
        legacy_combo = SimpleNamespace(origin="TPE", destination="NRT")
        with (
            patch("app.scanner._scan_route_direction", side_effect=scan_direction),
            patch("app.scanner._persist_offers"),
            patch("app.scanner._record_price_history"),
            patch("app.scanner.build_round_trips", return_value=[legacy_combo]),
            patch("app.scanner.send_round_trip_alert") as notifier,
        ):
            with self.assertRaisesRegex(
                ScanHealthError, "required route TPE-CTS produced no round-trip",
            ):
                scan_all(notify=True, today=date(2026, 10, 14))
        notifier.assert_not_called()

    def test_legacy_offers_with_no_deal_combinations_succeeds(self) -> None:
        cfg = AppConfig.load(CONFIG_PATH)
        # Keep only undated legacy routes: zero qualifying combinations is a
        # legitimate no-deal result, not a source-health failure.
        cfg.routes = [r for r in cfg.routes if not r.departure_end]
        offer = FlightOffer(
            source="test", airline="BR", flight_number="BR123",
            origin="TPE", destination="NRT",
            departure_at=datetime(2026, 11, 10, 10),
            arrival_at=datetime(2026, 11, 10, 14),
            duration_minutes=240, stops=0, price_twd=20_000,
        )

        class LiveSource:
            name = "live-test"

        class LiveAggregator:
            sources = [LiveSource()]

        with (
            patch("app.scanner.get_config", return_value=cfg),
            patch("app.scanner.Aggregator", return_value=LiveAggregator()),
            patch("app.scanner._scan_route_direction", return_value=[offer]),
            patch("app.scanner._persist_offers"),
            patch("app.scanner._record_price_history"),
            patch("app.scanner.build_round_trips", return_value=[]),
            patch("app.scanner.send_round_trip_alert") as notifier,
        ):
            summary = scan_all(notify=True, today=date(2026, 11, 2))

        self.assertGreater(summary["total_offers"], 0)
        self.assertEqual(summary["round_trips"], 0)
        self.assertEqual(summary["round_trip_alerts_sent"], 0)
        notifier.assert_not_called()

    def test_config_has_requested_monitor(self) -> None:
        cfg = AppConfig.load(CONFIG_PATH)
        route = next(r for r in cfg.routes if (r.origin, r.destination) == ("TPE", "CTS"))
        self.assertEqual(route.airlines, ["BR", "JX"])
        self.assertEqual((route.departure_start, route.departure_end),
                         ("2026-10-10", "2026-10-31"))
        # Stored as return-date gaps (nights): 5/6/7 = 6/7/8 calendar days.
        self.assertEqual(route.stay_days, [5, 6, 7])
        self.assertEqual(route.alert_below, 20_000)
        self.assertEqual(route.top_n_alerts, 10)

    def test_dated_search_bypasses_source_sampling(self) -> None:
        source = ExactSource()
        aggregator = Aggregator([source])
        aggregator.search("TPE", "CTS", date(2026, 10, 15), exact_date=True)
        self.assertEqual((source.sampled, source.exact), (0, 1))

    def test_pairing_keeps_six_to_eight_calendar_day_trips_without_price_ceiling(self) -> None:
        departure = date(2026, 10, 15)
        outbound = [flight("out", departure, 12_000, "JX")]
        returns = [
            flight("in", departure + timedelta(days=days), 12_000, "BR")
            for days in (4, 5, 6, 7, 8)
        ]
        combos = pair_route(outbound, returns, [5, 6, 7], max_total=None)
        self.assertEqual([combo["stay"] for combo in combos], [5, 6, 7])
        self.assertTrue(all(combo["total"] == 24_000 for combo in combos))

    def test_pairing_deduplicates_historical_rows_by_round_trip_fingerprint(self) -> None:
        departure = date(2026, 10, 15)
        outbound = flight("out", departure, 12_000, "JX")
        inbound = flight("in", departure + timedelta(days=5), 8_000, "BR")

        # Repeated scans may persist identical Flight rows. Their Cartesian
        # product still represents one RoundTrip and must not violate its unique
        # fingerprint constraint.
        combos = pair_route(
            [outbound, outbound],
            [inbound, inbound],
            [5],
            max_total=None,
        )

        self.assertEqual(len(combos), 1)
        self.assertIs(combos[0]["out"], outbound)
        self.assertIs(combos[0]["ret"], inbound)

    def test_top_membership_identity_does_not_change_with_price(self) -> None:
        class Trip:
            origin = "TPE"
            destination = "CTS"
            out_airline = "JX"
            out_flight_number = "JX850"
            out_departure_at = datetime(2026, 10, 15, 9, 0)
            return_airline = "BR"
            return_flight_number = "BR115"
            return_departure_at = datetime(2026, 10, 21, 15, 0)
            total_price_twd = 19_000

        trip = Trip()
        before = round_trip_itinerary_fingerprint(trip)
        trip.total_price_twd = 22_000
        self.assertEqual(before, round_trip_itinerary_fingerprint(trip))

    def test_mock_source_can_never_enable_notifications(self) -> None:
        self.assertFalse(notifications_are_safe(True, ["mock"]))
        self.assertFalse(notifications_are_safe(True, ["travelpayouts", "mock"]))
        self.assertTrue(notifications_are_safe(True, ["travelpayouts", "google_flights"]))
        self.assertFalse(notifications_are_safe(False, ["travelpayouts"]))

    def test_legacy_routes_share_one_global_top_n(self) -> None:
        class Candidate:
            def __init__(self, origin: str, destination: str, price: int) -> None:
                self.origin = origin
                self.destination = destination
                self.total_price_twd = price

        candidates = [
            Candidate("TPE", "NRT", 10_000),
            Candidate("TPE", "KIX", 11_000),
            Candidate("TPE", "NRT", 12_000),
            Candidate("TPE", "CTS", 9_000),  # route-specific; excluded
        ]
        selected = select_top_for_routes(
            candidates,
            {("TPE", "NRT"), ("TPE", "KIX")},
            2,
        )
        self.assertEqual([r.total_price_twd for r in selected], [10_000, 11_000])

    def test_discord_failure_is_not_marked_delivered_when_configured(self) -> None:
        class Env:
            discord_webhook_url = "https://discord.invalid/webhook"

        # Telegram success must not suppress a retry of the required Discord delivery.
        self.assertFalse(required_delivery_succeeded(Env(), telegram_ok=True, discord_ok=False))
        self.assertTrue(required_delivery_succeeded(Env(), telegram_ok=False, discord_ok=True))

    def test_telegram_only_delivery_uses_telegram_result(self) -> None:
        class Env:
            discord_webhook_url = ""

        self.assertTrue(required_delivery_succeeded(Env(), telegram_ok=True, discord_ok=False))
        self.assertFalse(required_delivery_succeeded(Env(), telegram_ok=False, discord_ok=False))


if __name__ == "__main__":
    unittest.main()
