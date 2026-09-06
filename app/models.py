from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, unquote, urlparse

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
    rewards_url: str | None = None
    notes: str | None = None
    created_at: datetime = Field(default_factory=utcnow)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        return value or None

    @field_validator(
        "player_id",
        "score_location",
        "location_name",
        "display_name",
        "notes",
        "scores_url",
        "rewards_url",
    )
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class FriendsFile(BaseModel):
    # Site location record id (picker), distinct from scores URL location id.
    location_id: int = 42
    location_slug: str = "pointe-orlando"
    score_location_id: int = 41
    score_location_name: str = "orlando (pointe orlando)"
    friends: list[Friend] = Field(default_factory=list)


class LevelScore(BaseModel):
    game_id: int
    level: int
    score: int
    room_id: int | None = None
    game_slug: str | None = None
    game_name: str | None = None


class GameBest(BaseModel):
    slug: str
    name: str
    room_id: int | None = None
    best_score: int | None = None
    levels_completed: int | None = None
    rank: int | None = None
    level_scores: list[LevelScore] = Field(default_factory=list)


class Reward(BaseModel):
    id: int | None = None
    name: str
    slug: str | None = None
    cost: int | None = None
    in_stock: bool | None = None
    location_id: int | None = None
    status: int | str | None = None
    description: str | None = None
    minimum_rank: int | None = None
    limit_per_player: int | None = None


class PlayerSnapshot(BaseModel):
    friend_id: str
    display_name: str
    player_id: str | None = None
    player_name: str | None = None
    location_name: str | None = None
    location_id: int | None = None

    # Ranks / standing
    profile_rank: int | None = None  # player.player.rank (visible profile rank)
    player_rank: int | None = None  # playerLocation.playerRank
    standing: int | None = None  # leaderboard position
    yearly_rank: int | None = None
    overall_rank: int | None = None  # alias kept for older UI; mirrors profile_rank

    # Scores / progress
    total_score: int | None = None
    yearly_score: int | None = None
    levels_beat: int | None = None
    level_count: int | None = None
    coins: int | None = None
    stars: int | None = None

    games: list[GameBest] = Field(default_factory=list)
    level_scores: list[LevelScore] = Field(default_factory=list)
    rewards: list[Reward] = Field(default_factory=list)

    scores_url: str | None = None
    rewards_url: str | None = None
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
    """Parse Activate public player/game scores or rewards URLs."""
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
    *,
    kind: str = "scores",
) -> str:
    """Build a scores/rewards path, URL-encoding the location name segment."""
    loc = quote(location_name, safe="")
    base = f"/scores/{quote(player, safe='')}/{quote(str(score_location), safe='')}/{loc}"
    if game:
        return f"{base}/{quote(game, safe='')}/{kind}"
    return f"{base}/{kind}"


def rewards_url_from_scores_url(scores_url: str) -> str | None:
    raw = (scores_url or "").strip()
    if not raw:
        return None
    if raw.endswith("/scores"):
        return raw[: -len("scores")] + "rewards"
    if raw.endswith("/scores/"):
        return raw[: -len("scores/")] + "rewards"
    parsed = parse_scores_url(raw)
    if not parsed:
        return None
    path = build_player_scores_path(
        parsed.player,
        parsed.score_location,
        parsed.location_name,
        kind="rewards",
    )
    if raw.startswith("http"):
        origin = f"{urlparse(raw).scheme}://{urlparse(raw).netloc}"
        return origin + path
    return path
