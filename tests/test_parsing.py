from __future__ import annotations

import json
from pathlib import Path

from app.models import build_player_scores_path, parse_scores_url
from app.parsing import extract_inertia_page, parse_player_page, rank_snapshots


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_parse_scores_url_player_and_game():
    parts = parse_scores_url(
        "https://playactivate.com/scores/wes-demo/42/pointe-orlando/scores"
    )
    assert parts is not None
    assert parts.player == "wes-demo"
    assert parts.score_location == "42"
    assert parts.location_name == "pointe-orlando"
    assert parts.game is None

    game = parse_scores_url(
        "/scores/wes-demo/42/pointe-orlando/mega-laser/scores"
    )
    assert game is not None
    assert game.game == "mega-laser"


def test_build_player_scores_path():
    assert (
        build_player_scores_path("wes-demo", "42", "pointe-orlando")
        == "/scores/wes-demo/42/pointe-orlando/scores"
    )
    assert (
        build_player_scores_path("wes-demo", "42", "pointe-orlando", "arena")
        == "/scores/wes-demo/42/pointe-orlando/arena/scores"
    )


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
        friend_id="wes",
        display_name="Wes",
        scores_url="https://playactivate.com/scores/wes-demo/42/pointe-orlando/scores",
    )
    assert snap.player_name == "Wes"
    assert snap.total_score == 128400
    assert snap.standing == 42
    assert snap.levels_beat == 5
    assert snap.level_count == 48
    by_slug = {g.slug: g for g in snap.games}
    assert by_slug["mega-laser"].best_score == 15400  # max of two entries
    assert by_slug["arena"].best_score == 9800

    other = snap.model_copy(update={"friend_id": "b", "display_name": "B", "total_score": 200000})
    ranked = rank_snapshots([snap, other])
    assert ranked[0].display_name == "B"
    assert ranked[1].display_name == "Wes"
