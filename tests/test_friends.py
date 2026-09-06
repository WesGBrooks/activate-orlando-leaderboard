from __future__ import annotations

from pathlib import Path

from app.friends import DEFAULT_FRIENDS, FriendsStore, orlando_scores_url


def test_default_seed_four_confirmed_orlando_friends():
    by_name = {f.display_name: f for f in DEFAULT_FRIENDS.friends}
    assert set(by_name) == {
        "GibsonLeader",
        "TikimanTim",
        "HeavenlyKevinT",
        "yourfriendlyneighborhoodtherapist",
    }

    gibson = by_name["GibsonLeader"]
    assert gibson.email == "wesgbrooks@gmail.com"
    assert gibson.player_id == "gibsonleader"
    assert gibson.scores_url and "/gibsonleader/41/" in gibson.scores_url

    tiki = by_name["TikimanTim"]
    assert tiki.player_id == "TikimanTim"
    assert tiki.scores_url == (
        "https://playactivate.com/scores/TikimanTim/41/"
        "orlando%20(pointe%20orlando)/scores"
    )

    kevin = by_name["HeavenlyKevinT"]
    assert kevin.player_id == "HeavenlyKevinT"
    assert "/HeavenlyKevinT/41/" in kevin.scores_url

    rey = by_name["yourfriendlyneighborhoodtherapist"]
    assert rey.email == "reyrivera09@gmail.com"
    assert rey.player_id == "yourfriendlyneighborhoodtherapist"
    assert rey.pending_resolution is False
    assert rey.scores_url == (
        "https://playactivate.com/scores/yourfriendlyneighborhoodtherapist/41/"
        "orlando%20(pointe%20orlando)/scores"
    )
    assert "NOT Amalikite" in (rey.notes or "")
    assert all(f.score_location == "41" for f in DEFAULT_FRIENDS.friends)
    assert all(f.location_name == "orlando (pointe orlando)" for f in DEFAULT_FRIENDS.friends)
    assert all(f.scores_url for f in DEFAULT_FRIENDS.friends)


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
    assert store.remove(friend.id) is True


def test_add_friend_from_handle_preserves_casing(tmp_path: Path):
    store = FriendsStore(tmp_path / "friends.json")
    friend = store.add_from_input(display_name="HeavenlyKevinT", identifier="HeavenlyKevinT")
    assert friend.player_id == "HeavenlyKevinT"
    assert friend.scores_url == orlando_scores_url("HeavenlyKevinT")


def test_add_friend_from_email(tmp_path: Path):
    store = FriendsStore(tmp_path / "friends.json")
    friend = store.add_from_input(display_name="Rey", identifier="ReyRivera09@gmail.com")
    assert friend.email == "reyrivera09@gmail.com"
    assert friend.scores_url is None


def test_migrates_pending_rey_to_therapist(tmp_path: Path):
    path = tmp_path / "friends.json"
    path.write_text(
        '''{
          "location_id": 42,
          "location_slug": "pointe-orlando",
          "friends": [
            {
              "id": "reyrivera09",
              "display_name": "ReyRivera09",
              "email": "reyrivera09@gmail.com",
              "pending_resolution": true,
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
    assert "GibsonLeader" in friends or any(f.email == "wesgbrooks@gmail.com" for f in store.list_friends())
    assert friends["TikimanTim"].player_id == "TikimanTim"
    assert "/TikimanTim/41/" in friends["TikimanTim"].scores_url
    assert "HeavenlyKevinT" in friends
    therapist = friends["yourfriendlyneighborhoodtherapist"]
    assert therapist.email == "reyrivera09@gmail.com"
    assert therapist.pending_resolution is False
    assert "/yourfriendlyneighborhoodtherapist/41/" in therapist.scores_url
    assert not any(f.id == "reyrivera09" for f in store.list_friends())
