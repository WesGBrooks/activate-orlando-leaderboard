from __future__ import annotations

from pathlib import Path

from app.friends import FriendsStore


def test_add_friend_from_scores_url(tmp_path: Path):
    store = FriendsStore(tmp_path / "friends.json")
    friend = store.add_from_input(
        display_name="Wes",
        identifier="https://playactivate.com/scores/wes-demo/42/pointe-orlando/scores",
    )
    assert friend.player_id == "wes-demo"
    assert friend.score_location == "42"
    assert friend.location_name == "pointe-orlando"
    assert friend.scores_url.endswith("/pointe-orlando/scores")
    assert store.get(friend.id) is not None
    assert store.remove(friend.id) is True


def test_add_friend_from_email(tmp_path: Path):
    store = FriendsStore(tmp_path / "friends.json")
    friend = store.add_from_input(display_name="Wes", identifier="wesgbrooks@gmail.com")
    assert friend.email == "wesgbrooks@gmail.com"
    assert friend.player_id is None
