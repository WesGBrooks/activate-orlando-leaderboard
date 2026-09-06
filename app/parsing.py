from __future__ import annotations

import json
import re
from html import unescape
from typing import Any

from app.config import ORLANDO_GAMES, ORLANDO_ROOM_IDS
from app.models import GameBest, LevelScore, PlayerSnapshot, Reward, utcnow

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


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def _room_maps(location: dict[str, Any]) -> tuple[dict[int, str], dict[int, str]]:
    """Return room_id -> name and room_id -> slug maps."""
    names: dict[int, str] = {}
    slugs: dict[int, str] = {}
    rooms = location.get("rooms") or []
    if isinstance(rooms, list):
        for room in rooms:
            if not isinstance(room, dict):
                continue
            rid = _as_int(room.get("id"))
            if rid is None:
                continue
            name = str(room.get("name") or rid)
            names[rid] = name
            slugs[rid] = _slugify(name)
    # Fall back to configured Orlando rooms.
    for room_id, slug, name in ORLANDO_ROOM_IDS:
        names.setdefault(room_id, name)
        slugs.setdefault(room_id, slug)
    return names, slugs


def _score_entries(player_location: dict[str, Any]) -> list[dict[str, Any]]:
    scores = player_location.get("scores") or []
    if isinstance(scores, dict):
        return [v for v in scores.values() if isinstance(v, dict)]
    if isinstance(scores, list):
        return [s for s in scores if isinstance(s, dict)]
    return []


def _level_scores_and_games(
    scores: list[dict[str, Any]],
    *,
    room_names: dict[int, str],
    room_slugs: dict[int, str],
) -> tuple[list[LevelScore], list[GameBest]]:
    """Activate encodes room in gameId as room_id * 100 + variant; levelId is the level."""
    level_scores: list[LevelScore] = []
    buckets: dict[str, dict[str, Any]] = {}

    for entry in scores:
        game_id = _as_int(entry.get("gameId") or entry.get("game_id"))
        level = _as_int(entry.get("levelId") or entry.get("level_id") or entry.get("level"))
        score = _as_int(
            entry.get("highScore")
            or entry.get("high_score")
            or entry.get("bestScore")
            or entry.get("score")
        )
        if game_id is None or level is None or score is None:
            # Legacy string-slug payloads
            slug = (
                entry.get("gameSlug")
                or entry.get("game_slug")
                or entry.get("slug")
                or entry.get("game")
            )
            if isinstance(slug, dict):
                slug = slug.get("slug") or slug.get("name")
            if not slug:
                continue
            slug = _slugify(str(slug))
            name = str(entry.get("gameName") or entry.get("name") or slug)
            bucket = buckets.setdefault(
                slug,
                {
                    "name": name,
                    "room_id": None,
                    "best": None,
                    "levels": 0,
                    "level_scores": [],
                },
            )
            bucket["levels"] += 1
            if bucket["best"] is None or score is not None and score > bucket["best"]:
                if score is not None:
                    bucket["best"] = score
            continue

        room_id = game_id // 100
        name = room_names.get(room_id) or f"Game {room_id}"
        slug = room_slugs.get(room_id) or _slugify(name)
        ls = LevelScore(
            game_id=game_id,
            level=level,
            score=score,
            room_id=room_id,
            game_slug=slug,
            game_name=name,
        )
        level_scores.append(ls)
        bucket = buckets.setdefault(
            slug,
            {
                "name": name,
                "room_id": room_id,
                "best": None,
                "levels": 0,
                "level_scores": [],
            },
        )
        bucket["levels"] += 1
        bucket["level_scores"].append(ls)
        if bucket["best"] is None or score > bucket["best"]:
            bucket["best"] = score

    games = [
        GameBest(
            slug=slug,
            name=meta["name"],
            room_id=meta["room_id"],
            best_score=meta["best"],
            levels_completed=meta["levels"] or None,
            level_scores=sorted(meta["level_scores"], key=lambda x: (x.level, x.game_id)),
        )
        for slug, meta in buckets.items()
    ]
    # Stable Orlando order when known.
    order = {slug: idx for idx, (slug, _) in enumerate(ORLANDO_GAMES)}
    games.sort(key=lambda g: (order.get(g.slug, 999), -(g.best_score or 0), g.name.lower()))
    level_scores.sort(key=lambda s: (s.game_name or "", s.level, s.game_id))
    return level_scores, games


def parse_rewards_page(page: dict[str, Any]) -> list[Reward]:
    props = page.get("props") or {}
    raw = props.get("rewards") or []
    if not isinstance(raw, list):
        return []
    rewards: list[Reward] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("title")
        if not name:
            continue
        rewards.append(
            Reward(
                id=_as_int(item.get("id")),
                name=str(name),
                slug=str(item["slug"]) if item.get("slug") else None,
                cost=_as_int(item.get("cost") or item.get("price")),
                in_stock=item.get("isStocked") if "isStocked" in item else item.get("inStock"),
                location_id=_as_int(item.get("locationId") or item.get("location_id")),
                status=item.get("status"),
                description=str(item["description"]) if item.get("description") else None,
                minimum_rank=_as_int(item.get("minimumRank") or item.get("minimum_rank")),
                limit_per_player=_as_int(
                    item.get("limitPerPlayer") or item.get("limit_per_player")
                ),
            )
        )
    return rewards


def parse_player_page(
    page: dict[str, Any],
    *,
    friend_id: str,
    display_name: str,
    scores_url: str | None = None,
    rewards_url: str | None = None,
    rewards: list[Reward] | None = None,
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
    room_names, room_slugs = _room_maps(location)

    player_name = (
        player_location.get("playerName")
        or inner.get("playerName")
        or inner.get("name")
        or player_wrap.get("playerName")
        or display_name
    )
    scores = _score_entries(player_location)
    level_scores, games = _level_scores_and_games(
        scores, room_names=room_names, room_slugs=room_slugs
    )

    profile_rank = _as_int(inner.get("rank"))
    player_rank = _as_int(player_location.get("playerRank") or player_location.get("player_rank"))
    standing = _as_int(player_location.get("standing"))
    yearly_rank = _as_int(player_location.get("yearlyRank") or player_location.get("yearly_rank"))
    level_count = _as_int(
        location.get("levelCount") or location.get("level_count") or location.get("levels")
    )

    return PlayerSnapshot(
        friend_id=friend_id,
        display_name=display_name,
        player_id=str(
            player_wrap.get("id")
            or inner.get("id")
            or player_location.get("playerName")
            or ""
        )
        or None,
        player_name=str(player_name) if player_name else None,
        location_name=str(
            player_wrap.get("locationName")
            or location.get("name")
            or location.get("slug")
            or ""
        )
        or None,
        location_id=_as_int(
            player_wrap.get("locationId")
            or player_location.get("locationId")
            or location.get("id")
        ),
        profile_rank=profile_rank,
        player_rank=player_rank,
        standing=standing,
        yearly_rank=yearly_rank,
        overall_rank=profile_rank,
        total_score=_as_int(
            player_location.get("totalScore")
            or player_location.get("total_score")
            or player_wrap.get("totalScore")
        ),
        yearly_score=_as_int(
            player_location.get("yearlyScore") or player_location.get("yearly_score")
        ),
        levels_beat=len(scores) if scores else _as_int(player_location.get("levelsCompleted")),
        level_count=level_count,
        coins=_as_int(inner.get("coins")),
        stars=_as_int(inner.get("stars")),
        games=games,
        level_scores=level_scores,
        rewards=rewards or [],
        scores_url=scores_url,
        rewards_url=rewards_url,
        fetched_at=utcnow(),
        cache_hit=cache_hit,
        source=source,
        raw={
            "component": page.get("component"),
            "url": page.get("url"),
            "trophyProgress": player_location.get("trophyProgress"),
        },
    )


def rank_snapshots(snapshots: list[PlayerSnapshot]) -> list[PlayerSnapshot]:
    def key(snap: PlayerSnapshot) -> tuple:
        has = snap.total_score is not None
        standing = snap.standing if snap.standing is not None else 10**9
        return (0 if has else 1, -(snap.total_score or 0), standing, snap.display_name.lower())

    return sorted(snapshots, key=key)
