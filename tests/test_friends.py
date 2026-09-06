from __future__ import annotations

from pathlib import Path

from app.friends import DEFAULT_FRIENDS, FriendsStore, REY_PENDING_NOTES, orlando_scores_url


def test_default_seed_resolved_handles_and_pending_rey():
    by_name = {f.display_name: f for f in DEFAULT_FRIENDS.friends}
    assert set(by_name) == {"GibsonLeader", "TikimanTim", "HeavenlyKevinT", "ReyRivera09"}

    gibson = by_name["GibsonLeader"]
    assert gibson.player_id == "gibsonleader"
    assert gibson.scores_url and "/gibsonleader/41/" in gibson.scores_url

    tiki = by_name["TikimanTim"]
    assert tiki.player_id == "TikimanTim"
    assert tiki.scores_url == (
        "https://playactivate.com/scores/TikimanTim/41/"
        "orlando%20(pointe%20orlando)/scores"
    )
    assert tiki.rewards_url and tiki.rewards_url.endswith("/rewards")
    assert tiki.pending_resolution is False

    kevin = by_name["HeavenlyKevinT"]
    assert kevin.player_id == "HeavenlyKevinT"
    assert kevin.scores_url == (
        "https://playactivate.com/scores/HeavenlyKevinT/41/"
        "orlando%20(pointe%20orlando)/scores"
    )

    rey = by_name["ReyRivera09"]
    assert rey.email == "reyrivera09@gmail.com"
    assert rey.player_id is None
    assert rey.scores_url is None
    assert rey.pending_resolution is True
    assert "Amalikite" in (rey.notes or "")
    assert "yourfriendlyneighborhoodtherapist" in (rey.notes or "")
    assert "PENDING" in (rey.notes or "")
    assert "Amalikite" in REY_PENDING_NOTES


def test_add_friend_from_scores_url_preserves_casing(tmp_path: Path):
    store = FriendsStore(tmp_path / "friends.json")
    friend = store.add_from_input(
        display_name="TikimanTim",
        identifier=(
            "https://playactivate.com/scores/TikimanTim/41/"
            "orlando%20(pointe%20orlando)/scores"
        ),
    )
    assert friend.player_id == "TikimanTim"
    assert "/TikimanTim/41/" in friend.scores_url
    assert store.get(friend.id) is not None
    assert store.remove(friend.id) is True


def test_add_friend_from_handle_preserves_casing(tmp_path: Path):
    store = FriendsStore(tmp_path / "friends.json")
    friend = store.add_from_input(display_name="HeavenlyKevinT", identifier="HeavenlyKevinT")
    assert friend.player_id == "HeavenlyKevinT"
    assert friend.scores_url == orlando_scores_url("HeavenlyKevinT")
    assert friend.email is None


def test_add_friend_from_email(tmp_path: Path):
    store = FriendsStore(tmp_path / "friends.json")
    friend = store.add_from_input(display_name="Rey", identifier="ReyRivera09@gmail.com")
    assert friend.email == "reyrivera09@gmail.com"
    assert friend.player_id is None
    assert friend.scores_url is None


def test_bind_resolved_scores_blocked_while_pending(tmp_path: Path):
    store = FriendsStore(tmp_path / "friends.json")
    rey = next(f for f in store.list_friends() if f.id == "reyrivera09")
    assert rey.pending_resolution is True
    bound = store.bind_resolved_scores(
        rey.id,
        scores_url="https://playactivate.com/scores/Amalikite/41/orlando%20(pointe%20orlando)/scores",
        player_id="Amalikite",
    )
    assert bound is not None
    assert bound.pending_resolution is True
    assert bound.scores_url is None
    assert bound.player_id is None


def test_migrates_wrong_tiki_slug_and_keeps_rey_pending(tmp_path: Path):
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
            },
            {
              "id": "tikimantim",
              "display_name": "Tikimantim",
              "player_id": "tikimantim",
              "scores_url": "https://playactivate.com/scores/tikimantim/41/orlando%20%28pointe%20orlando%29/scores"
            }
          ]
        }'''
    )
    store = FriendsStore(path)
    friends = {f.display_name: f for f in store.list_friends()}
    assert "GibsonLeader" in friends
    assert friends["TikimanTim"].player_id == "TikimanTim"
    assert "/TikimanTim/41/" in friends["TikimanTim"].scores_url
    assert "HeavenlyKevinT" in friends
    assert friends["ReyRivera09"].pending_resolution is True
    assert friends["ReyRivera09"].scores_url is None
