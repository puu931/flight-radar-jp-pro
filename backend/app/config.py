from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT_DIR / "config.yaml"


@dataclass
class Route:
    origin: str
    destination: str
    max_price: int
    max_round_trip: int = 0  # 0 = use 2 * max_price as fallback


@dataclass
class Filters:
    direct_only: bool = True
    baggage_required: bool = True
    avoid_red_eye: bool = True
    departure_after: str = "08:00"
    arrival_before: str = "22:30"
    exclude_basic_fare: bool = True


@dataclass
class SearchSettings:
    future_days: int = 90
    trip_length_days: list[int] = field(default_factory=lambda: [3, 4, 5, 6, 7])
    currency: str = "TWD"


@dataclass
class TripSettings:
    type: str = "round_trip"  # round_trip | one_way
    stay_days: list[int] = field(default_factory=lambda: [4, 5, 6, 7])
    top_n_alerts: int = 5


@dataclass
class NotificationSettings:
    cooldown_hours: int = 24
    dedupe: bool = True


@dataclass
class AppConfig:
    airlines: list[str]
    routes: list[Route]
    filters: Filters
    search: SearchSettings
    trip: TripSettings
    notification: NotificationSettings

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "AppConfig":
        raw = yaml.safe_load(path.read_text())
        return cls(
            airlines=list(raw.get("airlines", [])),
            routes=[Route(**r) for r in raw.get("routes", [])],
            filters=Filters(**raw.get("filters", {})),
            search=SearchSettings(**raw.get("search", {})),
            trip=TripSettings(**raw.get("trip", {})),
            notification=NotificationSettings(**raw.get("notification", {})),
        )


@dataclass
class Env:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    chat_id: str = os.getenv("CHAT_ID", "")
    discord_webhook_url: str = os.getenv("DISCORD_WEBHOOK_URL", "")
    amadeus_api_key: str = os.getenv("AMADEUS_API_KEY", "")
    amadeus_api_secret: str = os.getenv("AMADEUS_API_SECRET", "")
    travelpayouts_token: str = os.getenv("TRAVELPAYOUTS_TOKEN", "")
    travelpayouts_marker: str = os.getenv("TRAVELPAYOUTS_MARKER", "")
    serpapi_key: str = os.getenv("SERPAPI_KEY", "")
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{ROOT_DIR/'flights.db'}")
    sources: list[str] = field(default_factory=lambda: [
        s.strip() for s in os.getenv("FLIGHT_SOURCES", "mock").split(",") if s.strip()
    ])
    usd_to_twd: float = float(os.getenv("USD_TO_TWD", "32.0"))
    jpy_to_twd: float = float(os.getenv("JPY_TO_TWD", "0.21"))


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return AppConfig.load()


@lru_cache(maxsize=1)
def get_env() -> Env:
    return Env()
