from __future__ import annotations

import json
from pathlib import Path

from app.models import build_player_scores_path, parse_scores_url, rewards_url_from_scores_url
from app.parsing import extract_inertia_page, parse_player_page, parse_rewards_page, rank_snapshots


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_parse_scores_url_player_and_game():
    parts = parse_scores_url(
        "https://playactivate.com/scores/gibsonleader/41/orlando%20(pointe%20orlando)/scores"
    )
    assert parts is not None
    assert parts.player == "gibsonleader"
    assert parts.score_location == "41"
    assert parts.location_name == "orlando (pointe orlando)"
    assert parts.game is None

    game = parse_scores_url(
        "/scores/gibsonleader/41/orlando (pointe orlando)/mega-laser/scores"
    )
    assert game is not None
    assert game.game == "mega-laser"


def test_build_player_scores_path_and_rewards_url():
    path = build_player_scores_path(
        "gibsonleader", "41", "orlando (pointe orlando)"
    )
    assert path == "/scores/gibsonleader/41/orlando%20%28pointe%20orlando%29/scores"
    rewards = rewards_url_from_scores_url(
        "https://playactivate.com/scores/gibsonleader/41/orlando%20%28pointe%20orlando%29/scores"
    )
    assert rewards.endswith("/rewards")


def test_extract_inertia_page_from_html():
    page = {"component": "Site/Scores/Player", "props": {"player": {}}, "url": "/x", "version": "1"}
    html = (
        "<html><body><script type=\"application/json\" data-page=\"app\">"
        + json.dumps(page)
        + "</script></body></html>"
    )
    extracted = extract_inertia_page(html)
    assert extracted is not None
    assert extracted["component"] == "Site/Scores/Player"


def test_parse_player_page_and_rank():
    page = json.loads((FIXTURES / "sample_player_page.json").read_text())
    snap = parse_player_page(
        page,
        friend_id="gibsonleader",
        display_name="GibsonLeader",
        scores_url="https://playactivate.com/scores/gibsonleader/41/orlando%20%28pointe%20orlando%29/scores",
    )
    assert snap.player_name == "GibsonLeader"
    assert snap.total_score == 110025
    assert snap.standing == 7115
    assert snap.profile_rank == 3
    assert snap.player_rank == 4
    assert snap.yearly_rank == 2436
    assert snap.levels_beat == 36
    assert snap.level_count == 480
    assert snap.stars == 195
    assert snap.coins == 56
    by_slug = {g.slug: g for g in snap.games}
    assert by_slug["hoops"].best_score == 6346
    assert by_slug["mega-laser"].best_score == 3696
    assert by_slug["control"].best_score == 5619
    assert len(snap.level_scores) >= 20

    other = snap.model_copy(update={"friend_id": "b", "display_name": "B", "total_score": 200000})
    ranked = rank_snapshots([snap, other])
    assert ranked[0].display_name == "B"
    assert ranked[1].display_name == "GibsonLeader"


def test_parse_rewards_page():
    page = json.loads((FIXTURES / "sample_rewards_page.json").read_text())
    rewards = parse_rewards_page(page)
    assert len(rewards) >= 1
    assert rewards[0].name
    assert rewards[0].location_id == 41
