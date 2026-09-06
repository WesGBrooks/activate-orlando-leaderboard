from __future__ import annotations

import json
import re
from html import unescape
from typing import Any

from app.config import ORLANDO_GAMES
from app.models import GameBest, PlayerSnapshot, utcnow

_DATA_PAGE_RE = re.compile(
    r"<script[^>]*data-page=[\"']app[\"'][^>]*type=[\"']application/json[\"'][^>]*>(.*?)</script>",
    re.I | re.S,
)
_DATA_PAGE_RE_2 = re.compile(
    r"<script[^>]*type=[\"']application/json[\"'][^>]*data-page=[\"']app[\"'][^>]*>(.*?)</script>",
    re.I | re.S,
)


def extract_inertia_page(html: str) -> dict[str, Any] | None:
    text = html or ""
    for pattern in (_DATA_PAGE_RE, _DATA_PAGE_RE_2):
        match = pattern.search(text)
        if not match:
            continue
        raw = unescape(match.group(1)).strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            continue
    stripped = text.strip()
    if stripped.startswith("{") and '"component"' in stripped:
        try:
            data = json.loads(stripped)
            if isinstance(data, dict) and "component" in data:
                return data
        except json.JSONDecodeError:
            return None
    return None


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace("#", "").strip()
        if not cleaned:
            return None
        try:
            return int(float(cleaned))
        except ValueError:
            return None
    return None


def _game_name(slug: str) -> str:
    for known, name in ORLANDO_GAMES:
        if known == slug:
            return name
    return slug.replace("-", " ").title()


def _score_entries(player_location: dict[str, Any]) -> list[dict[str, Any]]:
    scores = player_location.get("scores") or []
    if isinstance(scores, dict):
        return [v for v in scores.values() if isinstance(v, dict)]
    if isinstance(scores, list):
        return [s for s in scores if isinstance(s, dict)]
    return []


def _best_by_game(scores: list[dict[str, Any]]) -> list[GameBest]:
    buckets: dict[str, dict[str, Any]] = {}
    for entry in scores:
        slug = (
            entry.get("gameSlug")
            or entry.get("game_slug")
            or entry.get("roomSlug")
            or entry.get("room_slug")
            or entry.get("slug")
            or entry.get("game")
        )
        if isinstance(slug, dict):
            slug = slug.get("slug") or slug.get("name")
        if not slug:
            slug = entry.get("gameName") or entry.get("game_name") or entry.get("name")
        if not slug:
            continue
        slug = str(slug).strip().lower().replace(" ", "-")
        score = _as_int(
            entry.get("highScore")
            or entry.get("high_score")
            or entry.get("bestScore")
            or entry.get("best_score")
            or entry.get("score")
            or entry.get("points")
        )
        bucket = buckets.setdefault(
            slug,
            {"best": None, "levels": 0, "rank": None, "name": _game_name(slug)},
        )
        bucket["levels"] += 1
        if score is not None and (bucket["best"] is None or score > bucket["best"]):
            bucket["best"] = score
        rank = _as_int(entry.get("rank") or entry.get("standing") or entry.get("position"))
        if rank is not None:
            bucket["rank"] = rank
        pretty = entry.get("gameName") or entry.get("game_name") or entry.get("roomName")
        if pretty:
            bucket["name"] = str(pretty)

    games = [
        GameBest(
            slug=slug,
            name=meta["name"],
            best_score=meta["best"],
            levels_completed=meta["levels"] or None,
            rank=meta["rank"],
        )
        for slug, meta in buckets.items()
    ]
    games.sort(key=lambda g: (-(g.best_score or 0), g.name.lower()))
    return games


def parse_player_page(
    page: dict[str, Any],
    *,
    friend_id: str,
    display_name: str,
    scores_url: str | None = None,
    cache_hit: bool = False,
    source: str = "live",
) -> PlayerSnapshot:
    props = page.get("props") or {}
    player_wrap = props.get("player") if isinstance(props.get("player"), dict) else {}
    inner = player_wrap.get("player") if isinstance(player_wrap.get("player"), dict) else {}
    player_location = (
        player_wrap.get("playerLocation")
        if isinstance(player_wrap.get("playerLocation"), dict)
        else {}
    )
    location = player_wrap.get("location") if isinstance(player_wrap.get("location"), dict) else {}

    player_name = (
        inner.get("playerName")
        or inner.get("name")
        or player_wrap.get("playerName")
        or display_name
    )
    scores = _score_entries(player_location)
    games = _best_by_game(scores)

    games_prop = props.get("games") or []
    if isinstance(games_prop, list):
        names = {
            str(g.get("slug")): str(g.get("name") or g.get("slug"))
            for g in games_prop
            if isinstance(g, dict) and g.get("slug")
        }
        for game in games:
            if game.slug in names:
                game.name = names[game.slug]

    return PlayerSnapshot(
        friend_id=friend_id,
        display_name=display_name,
        player_id=str(player_wrap.get("id") or inner.get("id") or "") or None,
        player_name=str(player_name) if player_name else None,
        location_name=str(
            player_wrap.get("locationName")
            or location.get("name")
            or location.get("slug")
            or ""
        )
        or None,
        total_score=_as_int(
            player_location.get("totalScore")
            or player_location.get("total_score")
            or player_wrap.get("totalScore")
        ),
        standing=_as_int(
            player_location.get("standing")
            or player_location.get("playerRank")
            or player_location.get("rank")
        ),
        levels_beat=len(scores) if scores else _as_int(player_location.get("levelsCompleted")),
        level_count=_as_int(location.get("levelCount") or location.get("level_count")),
        coins=_as_int(inner.get("coins")),
        stars=_as_int(inner.get("stars")),
        overall_rank=_as_int(inner.get("rank")),
        games=games,
        scores_url=scores_url,
        fetched_at=utcnow(),
        cache_hit=cache_hit,
        source=source,
        raw={"component": page.get("component"), "url": page.get("url")},
    )


def rank_snapshots(snapshots: list[PlayerSnapshot]) -> list[PlayerSnapshot]:
    def key(snap: PlayerSnapshot) -> tuple:
        has = snap.total_score is not None
        standing = snap.standing if snap.standing is not None else 10**9
        return (0 if has else 1, -(snap.total_score or 0), standing, snap.display_name.lower())

    return sorted(snapshots, key=key)
