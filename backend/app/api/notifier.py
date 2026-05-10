from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter

from ..config import get_env
from ..notifier import _send_discord, _send_telegram
from ..sources.base import FlightOffer

router = APIRouter()


def _sample_offer() -> FlightOffer:
    dep = datetime.utcnow() + timedelta(days=14)
    return FlightOffer(
        source="test",
        airline="BR",
        flight_number="BR198",
        origin="TPE",
        destination="NRT",
        departure_at=dep,
        arrival_at=dep + timedelta(hours=3),
        duration_minutes=180,
        stops=0,
        price_twd=7800.0,
        baggage_included=True,
        fare_class="economy",
        deep_link="https://www.evaair.com/",
    )


@router.post("/test")
def send_test_alert() -> dict:
    """Send a sample alert to whichever channels are configured.
    Bypasses dedupe/cooldown — purely for verifying credentials.
    """
    env = get_env()
    offer = _sample_offer()

    has_telegram = bool(env.bot_token and env.chat_id)
    has_discord = bool(env.discord_webhook_url)

    result = {
        "telegram_configured": has_telegram,
        "discord_configured": has_discord,
        "telegram_sent": False,
        "discord_sent": False,
    }
    if has_telegram:
        result["telegram_sent"] = _send_telegram(offer)
    if has_discord:
        result["discord_sent"] = _send_discord(offer)

    if not has_telegram and not has_discord:
        result["error"] = (
            "No credentials configured. Set BOT_TOKEN+CHAT_ID and/or DISCORD_WEBHOOK_URL in .env, "
            "then restart the backend."
        )
    return result
