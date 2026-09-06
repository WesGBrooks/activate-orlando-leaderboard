from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path

from app.models import (
    Friend,
    FriendsFile,
    build_player_scores_path,
    parse_scores_url,
    rewards_url_from_scores_url,
)

ACTIVATE_ORIGIN = "https://playactivate.com"
ORLANDO_SCORE_LOCATION = "41"
ORLANDO_SCORE_LOCATION_NAME = "orlando (pointe orlando)"


def orlando_scores_url(player_slug: str) -> str:
    path = build_player_scores_path(
        player_slug.lower(),
        ORLANDO_SCORE_LOCATION,
        ORLANDO_SCORE_LOCATION_NAME,
    )
    return f"{ACTIVATE_ORIGIN}{path}"


def orlando_rewards_url(player_slug: str) -> str:
    return rewards_url_from_scores_url(orlando_scores_url(player_slug)) or (
        orlando_scores_url(player_slug)[: -len("scores")] + "rewards"
    )


GIBSON_SCORES_URL = orlando_scores_url("gibsonleader")
GIBSON_REWARDS_URL = orlando_rewards_url("gibsonleader")
TIKI_SCORES_URL = orlando_scores_url("tikimantim")
TIKI_REWARDS_URL = orlando_rewards_url("tikimantim")
KEVIN_SCORES_URL = orlando_scores_url("heavenlykevint")
KEVIN_REWARDS_URL = orlando_rewards_url("heavenlykevint")

DEFAULT_FRIENDS = FriendsFile(
    location_id=42,
    location_slug="pointe-orlando",
    score_location_id=41,
    score_location_name=ORLANDO_SCORE_LOCATION_NAME,
    friends=[
        Friend(
            id="gibsonleader",
            display_name="GibsonLeader",
            email="wesgbrooks@gmail.com",
            player_id="gibsonleader",
            score_location=ORLANDO_SCORE_LOCATION,
            location_name=ORLANDO_SCORE_LOCATION_NAME,
            scores_url=GIBSON_SCORES_URL,
            rewards_url=GIBSON_REWARDS_URL,
            notes=(
                "Seeded from public Activate scores page. Refresh prefers GET on scores_url; "
                "site location record id is 42 / pointe-orlando, but scores URLs use location id 41."
            ),
        ),
        Friend(
            id="tikimantim",
            display_name="Tikimantim",
            player_id="tikimantim",
            score_location=ORLANDO_SCORE_LOCATION,
            location_name=ORLANDO_SCORE_LOCATION_NAME,
            scores_url=TIKI_SCORES_URL,
            rewards_url=TIKI_REWARDS_URL,
            notes="Seeded by Activate handle. Refresh via GET on scores_url.",
        ),
        Friend(
            id="heavenlykevint",
            display_name="HeavenlyKevinT",
            player_id="heavenlykevint",
            score_location=ORLANDO_SCORE_LOCATION,
            location_name=ORLANDO_SCORE_LOCATION_NAME,
            scores_url=KEVIN_SCORES_URL,
            rewards_url=KEVIN_REWARDS_URL,
            notes="Seeded by Activate handle. Refresh via GET on scores_url.",
        ),
        Friend(
            id="reyrivera09",
            display_name="ReyRivera09",
            email="reyrivera09@gmail.com",
            score_location=ORLANDO_SCORE_LOCATION,
            location_name=ORLANDO_SCORE_LOCATION_NAME,
            notes=(
                "Email seed. Resolve once via public POST /scores search to a stable "
                "player slug / scores_url, then refresh via GET."
            ),
        ),
    ],
)


class FriendsStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        if not self.path.exists():
            self.save(DEFAULT_FRIENDS)
        else:
            self._migrate_seed_if_needed()

    def _migrate_seed_if_needed(self) -> None:
        """Keep GibsonLeader URL seed healthy and merge any missing DEFAULT friends."""
        data = self.load()
        changed = False

        for idx, friend in enumerate(data.friends):
            if friend.id in {"wes", "gibsonleader"} or friend.email == "wesgbrooks@gmail.com":
                if not friend.scores_url or friend.player_id != "gibsonleader":
                    data.friends[idx] = DEFAULT_FRIENDS.friends[0].model_copy(deep=True)
                    changed = True

        existing_ids = {f.id for f in data.friends}
        existing_emails = {f.email for f in data.friends if f.email}
        existing_players = {(f.player_id or "").lower() for f in data.friends if f.player_id}

        for seed in DEFAULT_FRIENDS.friends:
            if seed.id in existing_ids:
                continue
            if seed.email and seed.email in existing_emails:
                continue
            if seed.player_id and seed.player_id.lower() in existing_players:
                continue
            data.friends.append(seed.model_copy(deep=True))
            changed = True

        data.score_location_id = 41
        data.score_location_name = ORLANDO_SCORE_LOCATION_NAME
        if data.location_slug != "pointe-orlando":
            data.location_slug = "pointe-orlando"
            changed = True
        if data.location_id != 42:
            data.location_id = 42
            changed = True
        if changed:
            self.save(data)

    def load(self) -> FriendsFile:
        with self._lock:
            return FriendsFile.model_validate(json.loads(self.path.read_text(encoding="utf-8")))

    def save(self, data: FriendsFile) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(data.model_dump_json(indent=2) + "\n", encoding="utf-8")

    def list_friends(self) -> list[Friend]:
        return list(self.load().friends)

    def get(self, friend_id: str) -> Friend | None:
        for friend in self.list_friends():
            if friend.id == friend_id:
                return friend
        return None

    def upsert(self, friend: Friend) -> Friend:
        data = self.load()
        for idx, existing in enumerate(data.friends):
            if existing.id == friend.id:
                data.friends[idx] = friend
                self.save(data)
                return friend
        data.friends.append(friend)
        self.save(data)
        return friend

    def remove(self, friend_id: str) -> bool:
        data = self.load()
        before = len(data.friends)
        data.friends = [f for f in data.friends if f.id != friend_id]
        self.save(data)
        return len(data.friends) < before

    def bind_resolved_scores(
        self,
        friend_id: str,
        *,
        scores_url: str,
        player_id: str | None = None,
        rewards_url: str | None = None,
        display_name: str | None = None,
    ) -> Friend | None:
        """Persist a one-time email/search resolution so later refreshes can GET."""
        friend = self.get(friend_id)
        if friend is None:
            return None
        parsed = parse_scores_url(scores_url)
        absolute = scores_url if scores_url.startswith("http") else f"{ACTIVATE_ORIGIN}{scores_url}"
        slug = player_id or (parsed.player if parsed else None) or friend.player_id
        updates: dict = {
            "scores_url": absolute,
            "rewards_url": rewards_url
            or rewards_url_from_scores_url(absolute)
            or friend.rewards_url,
        }
        if slug:
            updates["player_id"] = slug.lower()
        if parsed:
            updates["score_location"] = parsed.score_location
            updates["location_name"] = parsed.location_name
        if display_name and (
            not friend.display_name
            or friend.display_name.lower() == (friend.email or "").split("@")[0].lower()
        ):
            updates["display_name"] = display_name
        notes = friend.notes or ""
        if "Resolved from email search" not in notes:
            suffix = " Resolved from email search; later refreshes use GET on scores_url."
            updates["notes"] = (notes + suffix).strip() if notes else suffix.strip()
        bound = friend.model_copy(update=updates)
        return self.upsert(bound)

    def add_from_input(
        self,
        *,
        display_name: str,
        identifier: str,
        location_slug: str = "pointe-orlando",
        location_id: str = "41",
        location_name: str = ORLANDO_SCORE_LOCATION_NAME,
    ) -> Friend:
        identifier = identifier.strip()
        display_name = (display_name or "").strip() or identifier
        email = None
        player_id = None
        scores_url = None
        rewards_url = None
        score_location = location_id
        loc_name = location_name or location_slug

        if "playactivate.com" in identifier or identifier.startswith("/scores/"):
            parsed = parse_scores_url(identifier)
            if not parsed:
                raise ValueError(
                    "Could not parse scores URL. Expected "
                    "/scores/{player}/{scoreLocation}/{locationName}/scores"
                )
            player_id = parsed.player
            score_location = parsed.score_location
            loc_name = parsed.location_name
            scores_url = (
                identifier
                if identifier.startswith("http")
                else f"{ACTIVATE_ORIGIN}{identifier}"
            )
            if scores_url.endswith("/rewards"):
                rewards_url = scores_url
                scores_url = scores_url[: -len("rewards")] + "scores"
            else:
                rewards_url = rewards_url_from_scores_url(scores_url)
            if not display_name or display_name == identifier:
                display_name = player_id
        elif "@" in identifier:
            email = identifier.lower()
            if not display_name or display_name == identifier:
                display_name = email.split("@")[0]
        else:
            # Handle / player slug — build a stable Orlando scores URL for GET refresh.
            player_id = identifier.lower()
            if not display_name or display_name == identifier:
                display_name = identifier
            path = build_player_scores_path(player_id, score_location, loc_name)
            scores_url = f"{ACTIVATE_ORIGIN}{path}"
            rewards_url = rewards_url_from_scores_url(scores_url)

        friend = Friend(
            id=str(uuid.uuid4())[:8],
            display_name=display_name,
            player_id=player_id,
            email=email,
            score_location=score_location,
            location_name=loc_name,
            scores_url=scores_url,
            rewards_url=rewards_url,
        )
        return self.upsert(friend)
