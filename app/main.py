from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.activate import ActivateClient
from app.cache import ScoreCache
from app.config import ORLANDO_GAMES, Settings, get_settings
from app.friends import FriendsStore
from app.parsing import rank_snapshots

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Activate Orlando Friends Leaderboard", version="0.1.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def settings_dep() -> Settings:
    return get_settings()


def friends_dep(settings: Annotated[Settings, Depends(settings_dep)]) -> FriendsStore:
    return FriendsStore(settings.friends_path)


def client_dep(settings: Annotated[Settings, Depends(settings_dep)]) -> ActivateClient:
    cache = ScoreCache(settings.cache_db_path, ttl_seconds=settings.cache_ttl_seconds)
    return ActivateClient(settings, cache)


def _check_admin(settings: Settings, token: str | None) -> None:
    if not settings.admin_token:
        return
    if token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Invalid admin token")



async def _refresh_friend(
    client: ActivateClient,
    friends_store: FriendsStore,
    friend,
    *,
    force: bool = False,
):
    """Refresh one friend; persist email-search resolutions to a stable scores URL."""
    had_scores_url = bool(friend.scores_url)
    snap = await client.refresh_friend(friend, force=force)
    if (
        not had_scores_url
        and snap.scores_url
        and snap.source == "live"
        and not snap.error
    ):
        friends_store.bind_resolved_scores(
            friend.id,
            scores_url=snap.scores_url,
            player_id=snap.player_id,
            rewards_url=snap.rewards_url,
            display_name=snap.player_name,
        )
    return snap



@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def leaderboard(
    request: Request,
    settings: Annotated[Settings, Depends(settings_dep)],
    friends_store: Annotated[FriendsStore, Depends(friends_dep)],
    client: Annotated[ActivateClient, Depends(client_dep)],
    force: bool = Query(False),
) -> HTMLResponse:
    friends = friends_store.list_friends()
    snapshots = await asyncio.gather(
        *[_refresh_friend(client, friends_store, friend, force=force) for friend in friends]
    )
    ranked = rank_snapshots(list(snapshots))
    game_columns = [name for _, name in ORLANDO_GAMES]
    # Keep table readable: prefer games that anyone has a score for, else top defaults.
    seen = set()
    for snap in ranked:
        for game in snap.games:
            seen.add(game.slug)
    if seen:
        game_columns = [name for slug, name in ORLANDO_GAMES if slug in seen]
        game_slugs = [slug for slug, name in ORLANDO_GAMES if slug in seen]
    else:
        game_slugs = [slug for slug, _ in ORLANDO_GAMES[:8]]
        game_columns = [name for _, name in ORLANDO_GAMES[:8]]

    rows = []
    for idx, snap in enumerate(ranked, start=1):
        by_slug = {g.slug: g for g in snap.games}
        rows.append(
            {
                "rank": idx,
                "snap": snap,
                "game_scores": [by_slug.get(slug) for slug in game_slugs],
            }
        )

    demoish = any(s.source == "demo" for s in ranked)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "title": "Activate Orlando Friends",
            "location_name": settings.activate_location_name,
            "rows": rows,
            "game_columns": game_columns,
            "friends": friends,
            "demoish": demoish,
            "cache_ttl": settings.cache_ttl_seconds,
            "flash": request.query_params.get("flash"),
            "error": request.query_params.get("error"),
        },
    )


@app.post("/friends/add")
async def add_friend(
    settings: Annotated[Settings, Depends(settings_dep)],
    friends_store: Annotated[FriendsStore, Depends(friends_dep)],
    display_name: Annotated[str, Form()] = "",
    identifier: Annotated[str, Form()] = "",
    admin_token: Annotated[str, Form()] = "",
) -> RedirectResponse:
    _check_admin(settings, admin_token or None)
    try:
        friend = friends_store.add_from_input(
            display_name=display_name,
            identifier=identifier,
            location_slug=settings.activate_location_slug,
            location_id=str(settings.activate_score_location_id),
            location_name=settings.activate_score_location_name,
        )
    except ValueError as exc:
        return RedirectResponse(url=f"/?error={exc}", status_code=303)
    return RedirectResponse(
        url=f"/?flash=Added+{friend.display_name}",
        status_code=303,
    )


@app.post("/friends/{friend_id}/delete")
async def delete_friend(
    friend_id: str,
    settings: Annotated[Settings, Depends(settings_dep)],
    friends_store: Annotated[FriendsStore, Depends(friends_dep)],
    admin_token: Annotated[str, Form()] = "",
) -> RedirectResponse:
    _check_admin(settings, admin_token or None)
    friends_store.remove(friend_id)
    return RedirectResponse(url="/?flash=Friend+removed", status_code=303)


@app.post("/refresh")
async def refresh_all(
    settings: Annotated[Settings, Depends(settings_dep)],
    admin_token: Annotated[str, Form()] = "",
) -> RedirectResponse:
    _check_admin(settings, admin_token or None)
    return RedirectResponse(url="/?force=true&flash=Refreshing+scores", status_code=303)


@app.get("/api/leaderboard")
async def api_leaderboard(
    settings: Annotated[Settings, Depends(settings_dep)],
    friends_store: Annotated[FriendsStore, Depends(friends_dep)],
    client: Annotated[ActivateClient, Depends(client_dep)],
    force: bool = False,
) -> dict:
    friends = friends_store.list_friends()
    snapshots = await asyncio.gather(
        *[_refresh_friend(client, friends_store, friend, force=force) for friend in friends]
    )
    ranked = rank_snapshots(list(snapshots))
    return {
        "location": {
            "id": settings.activate_location_id,
            "slug": settings.activate_location_slug,
            "name": settings.activate_location_name,
            "score_location_id": settings.activate_score_location_id,
            "score_location_name": settings.activate_score_location_name,
        },
        "players": [snap.model_dump(mode="json") for snap in ranked],
    }
