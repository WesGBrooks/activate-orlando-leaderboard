from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path

from app.models import Friend, FriendsFile, parse_scores_url

DEFAULT_FRIENDS = FriendsFile(
    location_id=42,
    location_slug="pointe-orlando",
    friends=[
        Friend(
            id="wes",
            display_name="Wes",
            email="wesgbrooks@gmail.com",
            player_id=None,
            score_location="42",
            location_name="pointe-orlando",
            scores_url=None,
            notes=(
                "Seed placeholder. Look yourself up at https://playactivate.com/scores, "
                "open the Pointe Orlando player page, then paste that public scores URL "
                "(or player id) into this app's Friends form / data/friends.json."
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
        location_id: str = "42",
    ) -> Friend:
        identifier = identifier.strip()
        display_name = (display_name or "").strip() or identifier
        email = None
        player_id = None
        scores_url = None
        score_location = location_id
        location_name = location_slug

        if "playactivate.com" in identifier or identifier.startswith("/scores/"):
            parsed = parse_scores_url(identifier)
            if not parsed:
                raise ValueError(
                    "Could not parse scores URL. Expected "
                    "/scores/{player}/{scoreLocation}/pointe-orlando/scores"
                )
            player_id = parsed.player
            score_location = parsed.score_location
            location_name = parsed.location_name
            scores_url = (
                identifier
                if identifier.startswith("http")
                else f"https://playactivate.com{identifier}"
            )
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
            location_name=location_name,
            scores_url=scores_url,
        )
        return self.upsert(friend)
