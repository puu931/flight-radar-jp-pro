# ✈️ Flight Radar JP Pro (SaaS)

A flight price monitoring SaaS purpose-built for **Taiwan → Japan** routes.
Real-time alerts, price trends, low-fare calendar heatmap, multi-source aggregation.

---

## 🚀 Features

### ✈️ Flight search
- Taiwan (TPE / TSA / KHH) → Japan (NRT / HND / KIX / FUK / OKA / CTS)
- Scans next 90 days
- Displays in TWD
- Multi-source aggregation (Amadeus / Travelpayouts / Skyscanner / Kiwi / fallback crawler)

### 🛫 Airline whitelist
Only shows the following carriers:
- **BR** — EVA Air
- **JX** — Starlux Airlines
- **CI** — China Airlines

### 📊 SaaS Dashboard
- 📅 Calendar heatmap (low-fare calendar)
- 📈 Price trend chart
- ⚙️ Route settings
- 🔔 Alerts history

### 🔔 Notifications (Telegram + Discord)
- Real-time price alerts
- Telegram inline button (jump to booking)
- Discord rich embeds
- Send to either or both channels — set whichever credentials you have
- Deduplication
- Cooldown control

### 🧳 Smart filters
- Direct flights only
- Exclude red-eye flights
- Verify baggage included
- Auto-filter out basic fare

---

## 🧠 System Architecture

```
Frontend (Next.js)
├─ Dashboard
├─ Calendar 📅
├─ Trends 📈
└─ Settings ⚙️

Backend (FastAPI)
├─ Flight Engine
├─ Rule Engine
├─ Multi-source Aggregator
├─ Telegram Notifier
└─ Price History DB

Workers
├─ GitHub Actions Cron
├─ Fallback scanning
└─ Cache updater

Database
├─ flights
├─ price_history
├─ alerts_log
└─ users
```

---

## ⚙️ Configuration

See `config.yaml` for routes, airlines, filters, and search window.

Routes may override the global airline and stay-length filters. A route can
also set an exact `departure_start`/`departure_end`, an `alert_below`
round-trip threshold, and route-specific `top_n_alerts`. Dated routes scan
every configured date (including Google Flights); broad routes retain the
normal sampling strategy.

Live notifications require real data sources such as
`FLIGHT_SOURCES=travelpayouts,google_flights`. GitHub Actions validates its
runtime configuration before installing dependencies and refuses to scan when
`DATABASE_URL`, `DISCORD_WEBHOOK_URL`, or `FLIGHT_SOURCES` is missing.
`TRAVELPAYOUTS_TOKEN` is required when the Travelpayouts source is enabled. The
scheduled scan also rejects the synthetic `mock` source so a green workflow
always represents a live-data scan.

### Environment variables (`.env`)

```
BOT_TOKEN=...                # Telegram Bot token (optional)
CHAT_ID=...                  # Telegram Chat ID (optional)
DISCORD_WEBHOOK_URL=...      # Discord webhook URL (optional)
AMADEUS_API_KEY=...
AMADEUS_API_SECRET=...
TRAVELPAYOUTS_TOKEN=...      # optional
SERPAPI_KEY=...              # optional
DATABASE_URL=sqlite:///./flights.db
```

---

## 📋 Prerequisites

- **Python ≥ 3.10** (3.11 recommended; matches GitHub Actions)
- **Node.js ≥ 18.17** (20 LTS recommended for Next.js 14)

## 🧪 Backend Setup

```bash
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env   # then fill in keys
uvicorn app.main:app --reload --port 8000
```

API at <http://localhost:8000>, docs at <http://localhost:8000/docs>.

## 🌐 Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Dashboard at <http://localhost:3000>.

## 🔔 Notification Setup

You can use Telegram, Discord, or both. The notifier will send to whichever
channels have credentials configured.

### Telegram
1. Create a bot via [@BotFather](https://t.me/BotFather), copy `BOT_TOKEN`.
2. Talk to your bot once, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates` to get your `chat.id`.
3. Add `BOT_TOKEN` and `CHAT_ID` to GitHub repo Secrets (and your local `.env`).

### Discord
1. In Discord: server settings → **Integrations** → **Webhooks** → **New webhook**.
2. Pick the channel, give the bot a name, copy the **Webhook URL**.
3. Add `DISCORD_WEBHOOK_URL` to GitHub repo Secrets (and your local `.env`).

## ⏰ Scheduler (GitHub Actions)

The flight scan runs automatically at 09:00 / 15:00 / 23:00 JST. Supabase is
queried through PostgREST twice per day so its free-tier project remains active.
These checks are defined in `.github/workflows/scan.yml` and
`.github/workflows/keepalive.yml`.

GitHub can disable scheduled workflows in a public repository after 60 days
without repository activity, even when previous scheduled runs succeeded. The
`Repository Activity Heartbeat` workflow updates
`.github/repository-activity.txt` on the first day of each month. It may also be
run manually; a second run on the same UTC date exits without another commit.

### Health checks

- `Supabase Keep-Alive` must return HTTP 200 and the expected `keepalive_ping`
  row. A green run confirms a real database query, not only an HTTP health page.
- `Flight Scan` must pass the runtime configuration check and finish before its
  40-minute timeout. A successful scan can legitimately send zero alerts when
  every matching itinerary is already deduplicated or outside the thresholds.
- `Discord Webhook Test` is manual because it posts a real test message. Run it
  after rotating the webhook or when scans find qualifying fares but Discord
  receives nothing.
- `Repository Activity Heartbeat` should create at most one maintenance commit
  per UTC date and prevents the 60-day scheduled-workflow inactivity cutoff.

---

## 📅 Roadmap

- **v1 (MVP)** — flight scanning, Telegram alerts, filters ✅
- **v2 (Dashboard)** — calendar heatmap, price charts, settings UI ✅
- **v3 (SaaS)** — multi-user, subscriptions, full API, Google Flights fallback, advanced analytics

## 🧩 Tech Stack

Python (FastAPI) · Next.js 14 · SQLite → Postgres · Telegram Bot API · GitHub Actions · Playwright

## 📌 Goal

> ✈️ Personal Flight Intelligence System — optimised for **Taiwan → Japan** ticket decisions.

## 🛑 Disclaimer

This project is for educational and personal use.
Flight data sources may require API keys or partner agreements.
