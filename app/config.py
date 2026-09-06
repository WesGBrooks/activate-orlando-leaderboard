from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]

# Games listed on Activate public scores pages for Pointe Orlando.
ORLANDO_GAMES: list[tuple[str, str]] = [
    ("arena", "Arena"),
    ("climb", "Climb"),
    ("grid", "Grid"),
    ("hoops", "Hoops"),
    ("mega-laser", "Mega Laser"),
    ("pipes", "Pipes"),
    ("push", "Push"),
    ("trench", "Trench"),
    ("hide", "Hide"),
    ("control", "Control"),
    ("mega-grid", "Mega Grid"),
    ("laser", "Laser"),
    ("strike", "Strike"),
    ("portals", "Portals"),
    ("press", "Press"),
    ("scan", "Scan"),
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    activate_base_url: str = "https://playactivate.com"
    activate_location_id: int = 42
    activate_location_slug: str = "pointe-orlando"
    activate_location_name: str = "Orlando (Pointe Orlando)"

    cache_ttl_seconds: int = 600
    friends_path: Path = ROOT / "data" / "friends.json"
    cache_db_path: Path = ROOT / "data" / "cache.sqlite3"

    http_user_agent: str = (
        "activate-orlando-leaderboard/0.1 "
        "(+https://github.com/WesGBrooks/activate-orlando-leaderboard)"
    )
    activate_cookie: str | None = None

    demo_mode_fallback: bool = True
    force_demo_mode: bool = False

    host: str = "0.0.0.0"
    port: int = 8000
    admin_token: str | None = None

    min_request_interval_seconds: float = 1.25
    http_timeout_seconds: float = 25.0


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.friends_path.parent.mkdir(parents=True, exist_ok=True)
    settings.cache_db_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
