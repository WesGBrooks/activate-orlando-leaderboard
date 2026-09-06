from __future__ import annotations

from pathlib import Path

from app.friends import FriendsStore, DEFAULT_FRIENDS


def test_default_seed_is_gibsonleader():
    seed = DEFAULT_FRIENDS.friends[0]
    assert seed.display_name == "GibsonLeader"
    assert seed.player_id == "gibsonleader"
    assert seed.scores_url and "/gibsonleader/41/" in seed.scores_url
    assert seed.rewards_url and seed.rewards_url.endswith("/rewards")


def test_add_friend_from_scores_url(tmp_path: Path):
    store = FriendsStore(tmp_path / "friends.json")
    friend = store.add_from_input(
        display_name="GibsonLeader",
        identifier=(
            "https://playactivate.com/scores/gibsonleader/41/"
            "orlando%20%28pointe%20orlando%29/scores"
        ),
    )
    assert friend.player_id == "gibsonleader"
    assert friend.score_location == "41"
    assert friend.location_name == "orlando (pointe orlando)"
    assert "/41/" in friend.scores_url
    assert friend.rewards_url and friend.rewards_url.endswith("/rewards")
    assert store.get(friend.id) is not None
    assert store.remove(friend.id) is True


def test_add_friend_from_email(tmp_path: Path):
    store = FriendsStore(tmp_path / "friends.json")
    friend = store.add_from_input(display_name="Wes", identifier="wesgbrooks@gmail.com")
    assert friend.email == "wesgbrooks@gmail.com"
    assert friend.player_id is None


def test_migrates_old_wes_seed(tmp_path: Path):
    path = tmp_path / "friends.json"
    path.write_text(
        '''{
          "location_id": 42,
          "location_slug": "pointe-orlando",
          "friends": [
            {
              "id": "wes",
              "display_name": "Wes",
              "email": "wesgbrooks@gmail.com",
              "scores_url": null
            }
          ]
        }'''
    )
    store = FriendsStore(path)
    friends = store.list_friends()
    assert len(friends) == 1
    assert friends[0].player_id == "gibsonleader"
    assert friends[0].scores_url and "gibsonleader/41/" in friends[0].scores_url
