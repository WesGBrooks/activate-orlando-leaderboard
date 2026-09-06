from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]

# Display order for Orlando (Pointe Orlando) public score rooms.
ORLANDO_GAMES: list[tuple[str, str]] = [
    ("hoops", "Hoops"),
    ("grid", "Grid"),
    ("hide", "Hide"),
    ("mega-grid", "Mega Grid"),
    ("mega-laser", "Mega Laser"),
    ("control", "Control"),
    ("strike", "Strike"),
    ("portals", "Portals"),
    ("press", "Press"),
    ("scan", "Scan"),
]

# Room ids from Activate location.rooms on the Pointe Orlando scores page.
# Score rows encode room as gameId // 100.
ORLANDO_ROOM_IDS: list[tuple[int, str, str]] = [
    (10, "hoops", "Hoops"),
    (12, "grid", "Grid"),
    (20, "hide", "Hide"),
    (22, "mega-grid", "Mega Grid"),
    (23, "mega-laser", "Mega Laser"),
    (24, "control", "Control"),
    (25, "strike", "Strike"),
    (26, "portals", "Portals"),
    (27, "press", "Press"),
    (28, "scan", "Scan"),
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    activate_base_url: str = "https://playactivate.com"
    # Site location record / picker id.
    activate_location_id: int = 42
    activate_location_slug: str = "pointe-orlando"
    activate_location_name: str = "Orlando (Pointe Orlando)"
    # Scores URL location id/name (verified live for Pointe Orlando).
    activate_score_location_id: int = 41
    activate_score_location_name: str = "orlando (pointe orlando)"

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
    fetch_rewards: bool = True

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
