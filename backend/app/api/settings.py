from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter

from ..config import get_config
from ..schemas import RouteIn, SettingsOut

router = APIRouter()


@router.get("", response_model=SettingsOut)
def read_settings() -> SettingsOut:
    cfg = get_config()
    return SettingsOut(
        airlines=cfg.airlines,
        routes=[RouteIn(**asdict(r)) for r in cfg.routes],
        filters=asdict(cfg.filters),
        search=asdict(cfg.search),
        notification=asdict(cfg.notification),
    )
