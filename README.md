# ✈️ Flight Radar JP Pro (SaaS)

A flight price monitoring SaaS purpose-built for **Taiwan → Japan** routes.
Real-time alerts, price trends, low-fare calendar heatmap, multi-source aggregation.

---

## 🚀 Features

### ✈️ Flight search
- Taiwan (TPE / TSA / KHH) → Japan (NRT / HND / KIX / FUK / OKA)
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

Runs automatically at 09:00 / 15:00 / 23:00 JST.
See `.github/workflows/scan.yml`.

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
