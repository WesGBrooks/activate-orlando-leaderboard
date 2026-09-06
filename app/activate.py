from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import httpx

from app.cache import ScoreCache
from app.config import ORLANDO_GAMES, Settings
from app.models import (
    Friend,
    GameBest,
    PlayerSnapshot,
    build_player_scores_path,
    parse_scores_url,
    utcnow,
)
from app.parsing import extract_inertia_page, parse_player_page

logger = logging.getLogger(__name__)
_XSRF_RE = re.compile(r"XSRF-TOKEN=([^;]+)")


class ActivateClient:
    """Fetch Activate public scores pages with caching and polite rate limits."""

    def __init__(self, settings: Settings, cache: ScoreCache) -> None:
        self.settings = settings
        self.cache = cache
        self._lock = asyncio.Lock()
        self._last_request_at = 0.0
        self._fixtures = Path(__file__).resolve().parents[1] / "fixtures"

    def _headers(self, *, inertia: bool = False, xsrf: str | None = None) -> dict[str, str]:
        headers = {
            "User-Agent": self.settings.http_user_agent,
            "Accept": "text/html, application/xhtml+xml, application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": f"{self.settings.activate_base_url}/scores",
        }
        if self.settings.activate_cookie:
            headers["Cookie"] = self.settings.activate_cookie
        if inertia:
            headers["X-Inertia"] = "true"
            headers["X-Requested-With"] = "XMLHttpRequest"
            headers["Accept"] = "application/json"
        if xsrf:
            headers["X-XSRF-TOKEN"] = unquote(xsrf)
        return headers

    async def _throttle(self) -> None:
        async with self._lock:
            loop = asyncio.get_running_loop()
            now = loop.time()
            wait = self.settings.min_request_interval_seconds - (now - self._last_request_at)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_at = loop.time()

    def _cookies(self) -> httpx.Cookies | None:
        raw = self.settings.activate_cookie
        if not raw:
            return None
        cookies = httpx.Cookies()
        for part in raw.split(";"):
            if "=" not in part:
                continue
            name, value = part.split("=", 1)
            cookies.set(name.strip(), value.strip())
        return cookies

    def _cache_key(self, friend: Friend) -> str:
        if friend.scores_url:
            return f"url:{friend.scores_url}"
        return (
            f"player:{friend.player_id}:"
            f"{friend.score_location}:"
            f"{friend.location_name or self.settings.activate_location_slug}"
        )

    def _scores_path(self, friend: Friend) -> str | None:
        if friend.scores_url:
            parts = parse_scores_url(friend.scores_url)
            if parts:
                return build_player_scores_path(
                    parts.player,
                    parts.score_location,
                    parts.location_name,
                    parts.game,
                )
            return friend.scores_url
        if friend.player_id:
            return build_player_scores_path(
                friend.player_id,
                friend.score_location or str(self.settings.activate_location_id),
                friend.location_name or self.settings.activate_location_slug,
            )
        return None

    async def _get(
        self, client: httpx.AsyncClient, path: str, *, inertia: bool = False
    ) -> httpx.Response:
        await self._throttle()
        url = path if path.startswith("http") else f"{self.settings.activate_base_url}{path}"
        return await client.get(
            url, headers=self._headers(inertia=inertia), follow_redirects=True
        )

    async def fetch_locations(self) -> list[dict[str, Any]]:
        if self.settings.force_demo_mode:
            return self._demo_locations()
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.http_timeout_seconds,
                cookies=self._cookies(),
            ) as client:
                resp = await self._get(client, "/api/locations")
                if resp.status_code == 200 and "json" in resp.headers.get("content-type", ""):
                    data = resp.json()
                    return data if isinstance(data, list) else data.get("data", [])
        except Exception as exc:  # noqa: BLE001
            logger.warning("locations fetch failed: %s", exc)
        return self._demo_locations() if self.settings.demo_mode_fallback else []

    def _demo_locations(self) -> list[dict[str, Any]]:
        path = self._fixtures / "locations_orlando.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return [
            {
                "id": 42,
                "name": "Orlando (Pointe Orlando)",
                "slug": "pointe-orlando",
                "url": "https://playactivate.com/pointe-orlando",
            }
        ]

    async def refresh_friend(self, friend: Friend, *, force: bool = False) -> PlayerSnapshot:
        key = self._cache_key(friend)
        if not force:
            cached = self.cache.get(key)
            if cached:
                snap = PlayerSnapshot.model_validate(cached)
                snap.cache_hit = True
                snap.source = "cache"
                return snap

        if self.settings.force_demo_mode:
            return self._demo_snapshot(friend)

        path = self._scores_path(friend)
        if not path and friend.email:
            path = await self.try_search_player(friend.email)

        if not path:
            stale = self.cache.get_stale(key)
            if stale:
                snap = PlayerSnapshot.model_validate(stale)
                snap.cache_hit = True
                snap.source = "cache"
                snap.error = "No player id/scores URL yet; showing last cache if any."
                return snap
            if self.settings.demo_mode_fallback:
                return self._demo_snapshot(friend, reason="missing player id / scores URL")
            return PlayerSnapshot(
                friend_id=friend.id,
                display_name=friend.display_name,
                source="error",
                error=(
                    "Add this friend's public Activate scores URL or player id. "
                    "Email-only lookup is often blocked by Cloudflare from cloud hosts."
                ),
                fetched_at=utcnow(),
            )

        try:
            async with httpx.AsyncClient(
                timeout=self.settings.http_timeout_seconds,
                cookies=self._cookies(),
            ) as client:
                resp = await self._get(client, path, inertia=True)
                page = None
                if resp.status_code == 200:
                    try:
                        page = resp.json()
                    except Exception:  # noqa: BLE001
                        page = extract_inertia_page(resp.text)
                if page is None:
                    resp = await self._get(client, path, inertia=False)
                    if resp.status_code == 200:
                        page = extract_inertia_page(resp.text)
                if not page:
                    raise RuntimeError(
                        f"Activate returned HTTP {resp.status_code} "
                        "(Cloudflare challenge or empty page)"
                    )

                scores_url = friend.scores_url or (
                    path
                    if path.startswith("http")
                    else f"{self.settings.activate_base_url}{path}"
                )
                snap = parse_player_page(
                    page,
                    friend_id=friend.id,
                    display_name=friend.display_name,
                    scores_url=scores_url,
                    cache_hit=False,
                    source="live",
                )
                if not snap.player_id and friend.player_id:
                    snap.player_id = friend.player_id
                self.cache.set(key, snap.model_dump(mode="json"))
                return snap
        except Exception as exc:  # noqa: BLE001
            logger.warning("refresh failed for %s: %s", friend.display_name, exc)
            stale = self.cache.get_stale(key)
            if stale:
                snap = PlayerSnapshot.model_validate(stale)
                snap.cache_hit = True
                snap.source = "cache"
                snap.error = f"Live refresh failed ({exc}); showing cached scores."
                return snap
            if self.settings.demo_mode_fallback:
                return self._demo_snapshot(friend, reason=str(exc))
            return PlayerSnapshot(
                friend_id=friend.id,
                display_name=friend.display_name,
                player_id=friend.player_id,
                scores_url=friend.scores_url,
                source="error",
                error=str(exc),
                fetched_at=utcnow(),
            )

    async def try_search_player(self, query: str) -> str | None:
        """Best-effort POST /scores search. Often blocked by Cloudflare."""
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.http_timeout_seconds,
                cookies=self._cookies(),
                follow_redirects=False,
            ) as client:
                await self._throttle()
                boot = await client.get(
                    f"{self.settings.activate_base_url}/scores",
                    headers=self._headers(),
                )
                xsrf = None
                blob = (
                    boot.headers.get("set-cookie", "")
                    + ";"
                    + (self.settings.activate_cookie or "")
                )
                match = _XSRF_RE.search(blob)
                if match:
                    xsrf = match.group(1)
                if not xsrf:
                    for cookie in client.cookies.jar:
                        if cookie.name == "XSRF-TOKEN":
                            xsrf = cookie.value
                            break
                page = extract_inertia_page(boot.text) or {}
                version = page.get("version") or ""
                await self._throttle()
                headers = self._headers(inertia=True, xsrf=xsrf)
                if version:
                    headers["X-Inertia-Version"] = str(version)
                headers["Content-Type"] = "application/json"
                resp = await client.post(
                    f"{self.settings.activate_base_url}/scores",
                    headers=headers,
                    json={"search": query},
                )
                if resp.status_code in {301, 302, 303, 307, 308}:
                    location = resp.headers.get("location")
                    if location and "/scores/" in location:
                        return location
                if resp.status_code != 200:
                    logger.info("search %s => HTTP %s", query, resp.status_code)
                    return None
                try:
                    data = resp.json()
                except Exception:  # noqa: BLE001
                    data = extract_inertia_page(resp.text)
                if not data:
                    return None
                props = data.get("props") or {}
                players = props.get("players") or []
                if isinstance(players, list) and players:
                    first = players[0]
                    if isinstance(first, str):
                        return build_player_scores_path(
                            first,
                            str(self.settings.activate_location_id),
                            self.settings.activate_location_slug,
                        )
                    if isinstance(first, dict):
                        player = (
                            first.get("id")
                            or first.get("player")
                            or first.get("playerName")
                            or first.get("slug")
                        )
                        if player:
                            return build_player_scores_path(
                                str(player),
                                str(
                                    first.get("locationId")
                                    or self.settings.activate_location_id
                                ),
                                str(
                                    first.get("locationName")
                                    or self.settings.activate_location_slug
                                ),
                            )
                url = data.get("url") or ""
                if "/scores/" in str(url):
                    return str(url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("search failed for %s: %s", query, exc)
        return None

    def _demo_snapshot(self, friend: Friend, reason: str | None = None) -> PlayerSnapshot:
        demo_path = self._fixtures / "demo_players.json"
        players: list[dict[str, Any]] = []
        if demo_path.exists():
            players = json.loads(demo_path.read_text(encoding="utf-8"))
        match = None
        for entry in players:
            if entry.get("email") == friend.email or entry.get("id") == friend.id:
                match = entry
                break
            if friend.player_id and entry.get("player_id") == friend.player_id:
                match = entry
                break
        if match is None and players:
            match = players[sum(ord(c) for c in friend.id) % len(players)]
        if match is None:
            match = {"player_name": friend.display_name, "total_score": 0, "game_scores": {}}

        games: list[GameBest] = []
        for slug, name in ORLANDO_GAMES:
            score = (match.get("game_scores") or {}).get(slug)
            if score is not None:
                games.append(GameBest(slug=slug, name=name, best_score=int(score)))

        return PlayerSnapshot(
            friend_id=friend.id,
            display_name=friend.display_name,
            player_id=friend.player_id or match.get("player_id"),
            player_name=match.get("player_name") or friend.display_name,
            location_name=self.settings.activate_location_name,
            total_score=match.get("total_score"),
            standing=match.get("standing"),
            levels_beat=match.get("levels_beat"),
            level_count=match.get("level_count"),
            coins=match.get("coins"),
            stars=match.get("stars"),
            overall_rank=match.get("overall_rank"),
            games=games,
            scores_url=friend.scores_url,
            fetched_at=utcnow(),
            cache_hit=False,
            source="demo",
            error=(
                "Demo data — Activate live fetch unavailable"
                + (f" ({reason})" if reason else "")
                + ". Paste a public scores URL to bind a real player."
            ),
        )
