from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote, urlparse

from pydantic import BaseModel, Field, field_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Friend(BaseModel):
    id: str
    display_name: str
    player_id: str | None = None
    email: str | None = None
    score_location: str | None = None
    location_name: str | None = None
    scores_url: str | None = None
    notes: str | None = None
    created_at: datetime = Field(default_factory=utcnow)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        return value or None

    @field_validator("player_id", "score_location", "location_name", "display_name", "notes")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class FriendsFile(BaseModel):
    location_id: int = 42
    location_slug: str = "pointe-orlando"
    friends: list[Friend] = Field(default_factory=list)


class GameBest(BaseModel):
    slug: str
    name: str
    best_score: int | None = None
    levels_completed: int | None = None
    rank: int | None = None


class PlayerSnapshot(BaseModel):
    friend_id: str
    display_name: str
    player_id: str | None = None
    player_name: str | None = None
    location_name: str | None = None
    total_score: int | None = None
    standing: int | None = None
    levels_beat: int | None = None
    level_count: int | None = None
    coins: int | None = None
    stars: int | None = None
    overall_rank: int | None = None
    games: list[GameBest] = Field(default_factory=list)
    scores_url: str | None = None
    fetched_at: datetime | None = None
    cache_hit: bool = False
    source: str = "live"  # live | cache | demo | error
    error: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class ScoresUrlParts(BaseModel):
    player: str
    score_location: str
    location_name: str
    game: str | None = None


def parse_scores_url(url: str) -> ScoresUrlParts | None:
    """Parse Activate public player/game scores URLs."""
    raw = (url or "").strip()
    if not raw:
        return None
    if raw.startswith("/") and "://" not in raw:
        raw = "https://playactivate.com" + raw
    parsed = urlparse(raw)
    parts = [unquote(p) for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 4 or parts[0] != "scores":
        return None
    player, score_location, location_name = parts[1], parts[2], parts[3]
    game = None
    if len(parts) >= 5:
        if parts[-1] in {"scores", "rewards"}:
            if len(parts) >= 6:
                game = parts[4]
        else:
            game = parts[4]
    return ScoresUrlParts(
        player=player,
        score_location=score_location,
        location_name=location_name,
        game=game,
    )


def build_player_scores_path(
    player: str,
    score_location: str,
    location_name: str,
    game: str | None = None,
) -> str:
    base = f"/scores/{player}/{score_location}/{location_name}"
    if game:
        return f"{base}/{game}/scores"
    return f"{base}/scores"
