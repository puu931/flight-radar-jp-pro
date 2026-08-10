from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta

from app.config import AppConfig, CONFIG_PATH
from app.models import Flight
from app.notifier import required_delivery_succeeded, round_trip_itinerary_fingerprint
from app.round_trips import pair_route, select_top_for_routes
from app.scanner import notifications_are_safe
from app.sources.aggregator import Aggregator


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
