from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path

from app.models import Friend, FriendsFile, parse_scores_url, rewards_url_from_scores_url

GIBSON_SCORES_URL = (
    "https://playactivate.com/scores/gibsonleader/41/"
    "orlando%20%28pointe%20orlando%29/scores"
)
GIBSON_REWARDS_URL = (
    "https://playactivate.com/scores/gibsonleader/41/"
    "orlando%20%28pointe%20orlando%29/rewards"
)

DEFAULT_FRIENDS = FriendsFile(
    location_id=42,
    location_slug="pointe-orlando",
    score_location_id=41,
    score_location_name="orlando (pointe orlando)",
    friends=[
        Friend(
            id="gibsonleader",
            display_name="GibsonLeader",
            email="wesgbrooks@gmail.com",
            player_id="gibsonleader",
            score_location="41",
            location_name="orlando (pointe orlando)",
            scores_url=GIBSON_SCORES_URL,
            rewards_url=GIBSON_REWARDS_URL,
            notes=(
                "Seeded from public Activate scores page. Refresh prefers GET on scores_url; "
                "site location record id is 42 / pointe-orlando, but scores URLs use location id 41."
            ),
        )
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
        """Upgrade older Wes email-only seed to GibsonLeader scores URL."""
        data = self.load()
        changed = False
        for idx, friend in enumerate(data.friends):
            if friend.id in {"wes", "gibsonleader"} or friend.email == "wesgbrooks@gmail.com":
                if not friend.scores_url or friend.player_id != "gibsonleader":
                    data.friends[idx] = DEFAULT_FRIENDS.friends[0].model_copy(deep=True)
                    changed = True
        data.score_location_id = 41
        data.score_location_name = "orlando (pointe orlando)"
        if changed or data.location_slug != "pointe-orlando":
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

    def add_from_input(
        self,
        *,
        display_name: str,
        identifier: str,
        location_slug: str = "pointe-orlando",
        location_id: str = "41",
        location_name: str = "orlando (pointe orlando)",
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
                else f"https://playactivate.com{identifier}"
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
        else:
            player_id = identifier

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
