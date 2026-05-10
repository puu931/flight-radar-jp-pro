"""Google Flights scraper via Playwright.

Reality-check before reading further:
- Google Flights aggressively rotates anti-bot challenges. This scraper uses
  manual stealth tweaks and real-Chrome user-agent. As of 2026-05 it works
  from a residential IP (your Mac); from datacenter IPs (GitHub Actions) the
  block rate is much higher.
- Each (route, date) takes ~10-15s. We sample a subset of days per route
  rather than scanning all 90.
- Selectors rely on Chinese aria-labels (locale=zh-TW). If Google flips the
  locale or the page structure, parsing falls back to returning [].
- Dedicated to BR/JX prices — Travelpayouts already covers CI well.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime, time, timedelta
from typing import Optional

from .base import FlightOffer, FlightSource

log = logging.getLogger(__name__)

# Airline name (Google's display) → IATA code. Only carriers we care about.
AIRLINE_NAME_TO_CODE = {
    "中華航空": "CI",
    "長榮航空": "BR",
    "星宇航空": "JX",
    "日本航空": "JL",
    "全日空": "NH",
    "全日本空輸": "NH",
    "國泰航空": "CX",
    "新加坡航空": "SQ",
    "大韓航空": "KE",
    "韓亞航空": "OZ",
    # LCCs (intentionally listed so they get a code; airline whitelist filters them out)
    "台灣虎航": "IT",
    "捷星日本航空": "GK",
    "酷航": "TR",
    "泰國獅航": "SL",
    "樂桃航空": "MM",
    "亞洲航空": "AK",
    "越捷航空": "VZ",
}

# Days-from-today to sample. Spread across 90-day window.
SAMPLE_OFFSETS = [7, 14, 21, 30, 45, 60, 75]


def _parse_zh_time(s: str) -> Optional[time]:
    """Parse '下午2:25', '上午11:00', '中午12:10', '晚上7:25', '清晨6:35', '凌晨12:45'."""
    s = s.strip()
    m = re.match(r"(凌晨|清晨|早上|上午|中午|下午|晚上)?\s*(\d{1,2}):(\d{2})", s)
    if not m:
        return None
    period, hh, mm = m.group(1), int(m.group(2)), int(m.group(3))
    if period in ("下午", "晚上") and hh < 12:
        hh += 12
    if period == "中午" and hh != 12:
        hh = 12
    if period in ("上午", "早上", "清晨") and hh == 12:
        hh = 0
    if period == "凌晨" and hh == 12:
        hh = 0  # 凌晨12:45 means 00:45
    if hh > 23 or mm > 59:
        return None
    return time(hh, mm)


def _parse_duration_minutes(label: str) -> int:
    """Find '3 小時 10 分鐘' anywhere in label → 190."""
    h = re.search(r"(\d+)\s*小時", label)
    m = re.search(r"(\d+)\s*分鐘", label)
    return int(h.group(1) if h else 0) * 60 + int(m.group(1) if m else 0)


def _parse_aria_label(label: str, dep_date: date) -> Optional[dict]:
    """Parse a flight card's aria-label into structured fields.
    Example label:
      '8099 新台幣起。 搭乘星宇航空的直達航班。 星期三, 7月 1 下午3:00 於臺灣桃園國際機場出發，
       星期三, 7月 1 晚上7:25 抵達成田國際機場。 總交通時間：3 小時 25 分鐘   選擇航班'
    """
    if "新台幣" not in label or "搭乘" not in label:
        return None
    price_m = re.search(r"([\d,]+)\s*新台幣", label)
    airline_m = re.search(r"搭乘([^的]+?)的", label)
    direct = "直達" in label
    dep_time_m = re.search(r"(?:^|\s|，)((?:凌晨|清晨|早上|上午|中午|下午|晚上)?\s*\d{1,2}:\d{2})\s*於", label)
    arr_time_m = re.search(r"((?:凌晨|清晨|早上|上午|中午|下午|晚上)?\s*\d{1,2}:\d{2})\s*抵達", label)
    if not (price_m and airline_m and dep_time_m and arr_time_m):
        return None
    price = int(price_m.group(1).replace(",", ""))
    airline_name = airline_m.group(1).strip()
    dep_t = _parse_zh_time(dep_time_m.group(1))
    arr_t = _parse_zh_time(arr_time_m.group(1))
    if not dep_t or not arr_t:
        return None
    duration = _parse_duration_minutes(label)
    return {
        "price": price,
        "airline_name": airline_name,
        "direct": direct,
        "dep_time": dep_t,
        "arr_time": arr_t,
        "duration": duration,
    }


class GoogleFlightsSource(FlightSource):
    name = "google_flights"

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str, str], list[FlightOffer]] = {}

    def search(
        self,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> list[FlightOffer]:
        offset = (departure_date - date.today()).days
        if offset < 0 or offset not in SAMPLE_OFFSETS:
            return []
        key = (origin, destination, departure_date.isoformat())
        if key in self._cache:
            return self._cache[key]
        try:
            offers = asyncio.run(self._scrape_async(origin, destination, departure_date))
        except RuntimeError as e:
            # Already-running loop (e.g. when triggered from FastAPI) — skip cleanly.
            if "asyncio.run() cannot be called" in str(e) or "running event loop" in str(e):
                log.warning("Google Flights skipped: cannot run inside async loop. "
                            "Trigger via scripts/scan.py instead of API.")
                self._cache[key] = []
                return []
            log.warning("Google Flights scrape error %s→%s %s: %s",
                        origin, destination, departure_date, e)
            self._cache[key] = []
            return []
        except Exception as e:
            log.warning("Google Flights scrape failed %s→%s %s: %s",
                        origin, destination, departure_date, e)
            self._cache[key] = []
            return []
        self._cache[key] = offers
        return offers

    async def _scrape_async(
        self,
        origin: str,
        destination: str,
        dep_date: date,
    ) -> list[FlightOffer]:
        from playwright.async_api import async_playwright

        url = (
            "https://www.google.com/travel/flights?hl=zh-TW&curr=TWD"
            f"&q=Flights%20to%20{destination}%20from%20{origin}%20on%20{dep_date.isoformat()}%20one%20way%20nonstop"
        )
        offers: list[FlightOffer] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
                locale="zh-TW",
                timezone_id="Asia/Taipei",
                viewport={"width": 1440, "height": 900},
                extra_http_headers={"Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"},
            )
            await ctx.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
                "Object.defineProperty(navigator,'languages',{get:()=>['zh-TW','zh','en']});"
            )
            page = await ctx.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(5000)
                # Best-effort: expand "其他航班"
                try:
                    btns = await page.query_selector_all("button")
                    for b in btns:
                        txt = (await b.inner_text() or "").strip()
                        if "其他航班" in txt or "more flights" in txt.lower():
                            await b.click()
                            await page.wait_for_timeout(1500)
                            break
                except Exception:
                    pass

                cards = page.locator('[aria-label*="航班"]')
                n = await cards.count()
                seen_keys: set[tuple] = set()
                for i in range(min(n, 100)):
                    label = await cards.nth(i).get_attribute("aria-label") or ""
                    parsed = _parse_aria_label(label, dep_date)
                    if not parsed:
                        continue
                    code = AIRLINE_NAME_TO_CODE.get(parsed["airline_name"])
                    if not code:
                        continue
                    if not parsed["direct"]:
                        continue
                    dep_dt = datetime.combine(dep_date, parsed["dep_time"])
                    arr_dt = datetime.combine(dep_date, parsed["arr_time"])
                    if arr_dt < dep_dt:
                        arr_dt += timedelta(days=1)
                    # Dedupe within page (each card duplicates aria text in detail row)
                    fp = (code, dep_dt, parsed["price"])
                    if fp in seen_keys:
                        continue
                    seen_keys.add(fp)
                    offers.append(FlightOffer(
                        source=self.name,
                        airline=code,
                        flight_number=code,  # Google Flights aria doesn't expose flight #
                        origin=origin,
                        destination=destination,
                        departure_at=dep_dt,
                        arrival_at=arr_dt,
                        duration_minutes=parsed["duration"],
                        stops=0,
                        price_twd=float(parsed["price"]),
                        currency="TWD",
                        baggage_included=False,
                        fare_class="economy",
                        deep_link=url,
                    ))
            finally:
                await browser.close()
        log.info("Google Flights %s→%s %s: %d offers", origin, destination, dep_date, len(offers))
        return offers
