from __future__ import annotations

from pathlib import Path

from app.friends import DEFAULT_FRIENDS, FriendsStore, orlando_scores_url


def test_default_seed_includes_handles_and_email():
    names = {f.display_name for f in DEFAULT_FRIENDS.friends}
    assert names == {"GibsonLeader", "Tikimantim", "HeavenlyKevinT", "ReyRivera09"}

    by_name = {f.display_name: f for f in DEFAULT_FRIENDS.friends}
    gibson = by_name["GibsonLeader"]
    assert gibson.player_id == "gibsonleader"
    assert gibson.scores_url and "/gibsonleader/41/" in gibson.scores_url

    tiki = by_name["Tikimantim"]
    assert tiki.player_id == "tikimantim"
    assert tiki.scores_url == orlando_scores_url("tikimantim")
    assert tiki.rewards_url and tiki.rewards_url.endswith("/rewards")

    kevin = by_name["HeavenlyKevinT"]
    assert kevin.player_id == "heavenlykevint"
    assert kevin.scores_url == orlando_scores_url("heavenlykevint")

    rey = by_name["ReyRivera09"]
    assert rey.email == "reyrivera09@gmail.com"
    assert rey.player_id is None
    assert rey.scores_url is None


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


def test_add_friend_from_handle_builds_scores_url(tmp_path: Path):
    store = FriendsStore(tmp_path / "friends.json")
    friend = store.add_from_input(display_name="Tikimantim", identifier="Tikimantim")
    assert friend.player_id == "tikimantim"
    assert friend.scores_url == orlando_scores_url("tikimantim")
    assert friend.email is None


def test_add_friend_from_email(tmp_path: Path):
    store = FriendsStore(tmp_path / "friends.json")
    friend = store.add_from_input(display_name="Rey", identifier="ReyRivera09@gmail.com")
    assert friend.email == "reyrivera09@gmail.com"
    assert friend.player_id is None
    assert friend.scores_url is None


def test_bind_resolved_scores_persists_url(tmp_path: Path):
    store = FriendsStore(tmp_path / "friends.json")
    friend = store.add_from_input(display_name="Rey", identifier="ReyRivera09@gmail.com")
    bound = store.bind_resolved_scores(
        friend.id,
        scores_url=orlando_scores_url("reyrivera09"),
        player_id="reyrivera09",
    )
    assert bound is not None
    assert bound.player_id == "reyrivera09"
    assert bound.scores_url == orlando_scores_url("reyrivera09")
    assert bound.rewards_url and bound.rewards_url.endswith("/rewards")
    assert "Resolved from email search" in (bound.notes or "")


def test_migrates_old_wes_seed_and_merges_new_friends(tmp_path: Path):
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
    names = {f.display_name for f in friends}
    assert "GibsonLeader" in names
    assert "Tikimantim" in names
    assert "HeavenlyKevinT" in names
    assert "ReyRivera09" in names
    gibson = next(f for f in friends if f.display_name == "GibsonLeader")
    assert gibson.player_id == "gibsonleader"
    assert gibson.scores_url and "gibsonleader/41/" in gibson.scores_url
