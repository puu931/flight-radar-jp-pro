from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import alerts, calendar, flights, notifier, round_trips, settings, trends
from .db import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# Silence httpx's per-request URL logs — they leak query-string secrets.
logging.getLogger("httpx").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Flight Radar JP Pro",
    version="0.2.0",
    description="Taiwan → Japan flight price monitoring API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(flights.router, prefix="/api/flights", tags=["flights"])
app.include_router(calendar.router, prefix="/api/calendar", tags=["calendar"])
app.include_router(trends.router, prefix="/api/trends", tags=["trends"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(notifier.router, prefix="/api/notifier", tags=["notifier"])
app.include_router(round_trips.router, prefix="/api/round_trips", tags=["round_trips"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
