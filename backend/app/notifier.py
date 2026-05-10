from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select

from .config import get_config, get_env
from .db import session_scope
from .models import AlertLog
from .sources.base import FlightOffer

log = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

AIRLINE_NAME = {
    "BR": "EVA Air",
    "JX": "Starlux",
    "CI": "China Airlines",
}

# Discord embed accent (hex 0x5e9bff matches the dashboard accent).
DISCORD_COLOR = 0x5E9BFF


def fingerprint(offer: FlightOffer) -> str:
    key = f"{offer.origin}|{offer.destination}|{offer.airline}|{offer.flight_number}|{offer.departure_at.isoformat()}|{int(offer.price_twd)}"
    return hashlib.sha1(key.encode()).hexdigest()


def _format_text(offer: FlightOffer) -> str:
    """Plain text version, used for AlertLog.message and Discord fallback."""
    dep = offer.departure_at.strftime("%Y-%m-%d %H:%M")
    arr = offer.arrival_at.strftime("%H:%M")
    duration_h = offer.duration_minutes // 60
    duration_m = offer.duration_minutes % 60
    bag = "✅" if offer.baggage_included else "⚠️"
    return (
        f"✈️ {offer.origin} → {offer.destination}  TWD {int(offer.price_twd):,}\n"
        f"{offer.airline} {offer.flight_number}  {dep} → {arr}  ({duration_h}h{duration_m:02d}m)\n"
        f"行李 {bag}  艙等 {offer.fare_class}"
    )


def _format_telegram_html(offer: FlightOffer) -> str:
    dep = offer.departure_at.strftime("%Y-%m-%d %H:%M")
    arr = offer.arrival_at.strftime("%H:%M")
    duration_h = offer.duration_minutes // 60
    duration_m = offer.duration_minutes % 60
    bag = "✅" if offer.baggage_included else "⚠️"
    return (
        f"✈️ <b>{offer.origin} → {offer.destination}</b>  TWD <b>{int(offer.price_twd):,}</b>\n"
        f"{offer.airline} {offer.flight_number}  {dep} → {arr}  ({duration_h}h{duration_m:02d}m)\n"
        f"行李 {bag}  艙等 {offer.fare_class}"
    )


def _was_recently_alerted(fp: str, cooldown_hours: int) -> bool:
    cutoff = datetime.utcnow() - timedelta(hours=cooldown_hours)
    with session_scope() as db:
        row = db.execute(
            select(AlertLog)
            .where(AlertLog.fingerprint == fp)
            .where(AlertLog.sent_at >= cutoff)
            .limit(1)
        ).scalar_one_or_none()
        return row is not None


def _record_alert(offer: FlightOffer, fp: str, message: str, delivered: bool) -> None:
    with session_scope() as db:
        db.add(AlertLog(
            fingerprint=fp,
            origin=offer.origin,
            destination=offer.destination,
            airline=offer.airline,
            flight_number=offer.flight_number,
            departure_at=offer.departure_at,
            price_twd=offer.price_twd,
            delivered=delivered,
            message=message,
        ))


def _send_telegram(offer: FlightOffer) -> bool:
    env = get_env()
    if not env.bot_token or not env.chat_id:
        return False
    try:
        payload: dict = {
            "chat_id": env.chat_id,
            "text": _format_telegram_html(offer),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if offer.deep_link:
            payload["reply_markup"] = {
                "inline_keyboard": [[{"text": "🎫 立即訂票", "url": offer.deep_link}]]
            }
        r = httpx.post(TELEGRAM_API.format(token=env.bot_token), json=payload, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        log.warning("Telegram send failed: %s", e)
        return False


def _send_discord(offer: FlightOffer) -> bool:
    env = get_env()
    if not env.discord_webhook_url:
        return False
    dep = offer.departure_at.strftime("%Y-%m-%d %H:%M")
    arr = offer.arrival_at.strftime("%H:%M")
    duration_h = offer.duration_minutes // 60
    duration_m = offer.duration_minutes % 60
    bag = "✅" if offer.baggage_included else "⚠️ 不含"
    airline_name = AIRLINE_NAME.get(offer.airline, offer.airline)
    embed: dict = {
        "title": f"✈️ {offer.origin} → {offer.destination}  NT$ {int(offer.price_twd):,}",
        "description": (
            f"**{airline_name} ({offer.airline}) {offer.flight_number}**\n"
            f"🕐 {dep} → {arr}  ·  {duration_h}h{duration_m:02d}m\n"
            f"🧳 行李 {bag}  ·  艙等 `{offer.fare_class}`"
        ),
        "color": DISCORD_COLOR,
        "footer": {"text": f"source: {offer.source}"},
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    if offer.deep_link:
        embed["url"] = offer.deep_link
    payload = {"username": "Flight Radar JP", "embeds": [embed]}
    try:
        r = httpx.post(env.discord_webhook_url, json=payload, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        log.warning("Discord send failed: %s", e)
        return False


def _format_round_trip_text(rt) -> str:
    out_dep = rt.out_departure_at.strftime("%m/%d %H:%M")
    ret_dep = rt.return_departure_at.strftime("%m/%d %H:%M")
    return (
        f"✈️ {rt.origin}↔{rt.destination}  來回 NT$ {int(rt.total_price_twd):,}  ({rt.stay_days}天)\n"
        f"去 {rt.out_airline}{rt.out_flight_number} {out_dep}  NT$ {int(rt.out_price_twd):,}\n"
        f"回 {rt.return_airline}{rt.return_flight_number} {ret_dep}  NT$ {int(rt.return_price_twd):,}"
    )


def _send_telegram_round_trip(rt) -> bool:
    env = get_env()
    if not env.bot_token or not env.chat_id:
        return False
    out_dep = rt.out_departure_at.strftime("%Y-%m-%d %H:%M")
    ret_dep = rt.return_departure_at.strftime("%Y-%m-%d %H:%M")
    text = (
        f"✈️ <b>{rt.origin} ↔ {rt.destination}</b>  來回 <b>NT$ {int(rt.total_price_twd):,}</b>  ({rt.stay_days}天)\n"
        f"去 {rt.out_airline}{rt.out_flight_number} {out_dep}  NT$ {int(rt.out_price_twd):,}\n"
        f"回 {rt.return_airline}{rt.return_flight_number} {ret_dep}  NT$ {int(rt.return_price_twd):,}"
    )
    try:
        payload: dict = {
            "chat_id": env.chat_id, "text": text,
            "parse_mode": "HTML", "disable_web_page_preview": True,
        }
        buttons = []
        if rt.out_deep_link:
            buttons.append({"text": "🛫 訂去程", "url": rt.out_deep_link})
        if rt.return_deep_link:
            buttons.append({"text": "🛬 訂回程", "url": rt.return_deep_link})
        if buttons:
            payload["reply_markup"] = {"inline_keyboard": [buttons]}
        r = httpx.post(TELEGRAM_API.format(token=env.bot_token), json=payload, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        log.warning("Telegram round-trip send failed: %s", e)
        return False


def _send_discord_round_trip(rt) -> bool:
    env = get_env()
    if not env.discord_webhook_url:
        return False
    out_dep = rt.out_departure_at.strftime("%m/%d (%a) %H:%M")
    ret_dep = rt.return_departure_at.strftime("%m/%d (%a) %H:%M")
    out_name = AIRLINE_NAME.get(rt.out_airline, rt.out_airline)
    ret_name = AIRLINE_NAME.get(rt.return_airline, rt.return_airline)
    embed: dict = {
        "title": f"✈️ {rt.origin} ↔ {rt.destination}  來回 NT$ {int(rt.total_price_twd):,}",
        "description": (
            f"**停留 {rt.stay_days} 天**\n"
            f"🛫 **去** {out_name} ({rt.out_airline}) {rt.out_flight_number}\n"
            f"  {out_dep}  ·  NT$ {int(rt.out_price_twd):,}\n"
            f"🛬 **回** {ret_name} ({rt.return_airline}) {rt.return_flight_number}\n"
            f"  {ret_dep}  ·  NT$ {int(rt.return_price_twd):,}"
        ),
        "color": DISCORD_COLOR,
        "footer": {"text": "round-trip · top-cheapest"},
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    if rt.out_deep_link:
        embed["url"] = rt.out_deep_link
    payload = {"username": "Flight Radar JP", "embeds": [embed]}
    try:
        r = httpx.post(env.discord_webhook_url, json=payload, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        log.warning("Discord round-trip send failed: %s", e)
        return False


def send_round_trip_alert(rt) -> bool:
    """Send a round-trip combo alert to all configured channels with dedupe."""
    cfg = get_config()
    env = get_env()
    fp = "rt:" + rt.fingerprint
    if cfg.notification.dedupe and _was_recently_alerted(fp, cfg.notification.cooldown_hours):
        log.debug("Skipping duplicate round-trip alert: %s", fp)
        return False
    text = _format_round_trip_text(rt)
    has_any_channel = bool(env.bot_token and env.chat_id) or bool(env.discord_webhook_url)
    if not has_any_channel:
        log.info("[dry-run round-trip] %s", text.replace("\n", " | "))
        # Record fake AlertLog so dedupe still works in subsequent runs.
        with session_scope() as db:
            db.add(AlertLog(
                fingerprint=fp,
                origin=rt.origin, destination=rt.destination,
                airline=rt.out_airline, flight_number=rt.out_flight_number,
                departure_at=rt.out_departure_at, price_twd=rt.total_price_twd,
                delivered=False, message=text,
            ))
        return False
    tg_ok = _send_telegram_round_trip(rt)
    dc_ok = _send_discord_round_trip(rt)
    delivered = tg_ok or dc_ok
    with session_scope() as db:
        db.add(AlertLog(
            fingerprint=fp,
            origin=rt.origin, destination=rt.destination,
            airline=rt.out_airline, flight_number=rt.out_flight_number,
            departure_at=rt.out_departure_at, price_twd=rt.total_price_twd,
            delivered=delivered, message=text,
        ))
    if tg_ok and dc_ok:
        log.info("Round-trip alert sent to telegram + discord: %s", fp)
    elif tg_ok:
        log.info("Round-trip alert sent to telegram: %s", fp)
    elif dc_ok:
        log.info("Round-trip alert sent to discord: %s", fp)
    return delivered


def send_alert(offer: FlightOffer) -> bool:
    cfg = get_config()
    env = get_env()

    fp = fingerprint(offer)
    if cfg.notification.dedupe and _was_recently_alerted(fp, cfg.notification.cooldown_hours):
        log.debug("Skipping duplicate alert: %s", fp)
        return False

    text = _format_text(offer)
    has_any_channel = bool(env.bot_token and env.chat_id) or bool(env.discord_webhook_url)

    if not has_any_channel:
        log.info("[dry-run] %s", text.replace("\n", " | "))
        _record_alert(offer, fp, text, delivered=False)
        return False

    tg_ok = _send_telegram(offer)
    dc_ok = _send_discord(offer)
    delivered = tg_ok or dc_ok

    if tg_ok and dc_ok:
        log.info("Alert sent to telegram + discord: %s", fp)
    elif tg_ok:
        log.info("Alert sent to telegram: %s", fp)
    elif dc_ok:
        log.info("Alert sent to discord: %s", fp)

    _record_alert(offer, fp, text, delivered)
    return delivered
