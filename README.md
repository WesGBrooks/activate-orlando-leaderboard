# Activate Orlando Friends Leaderboard

A small FastAPI app so friends can compare [Activate](https://playactivate.com) scores for **Orlando (Pointe Orlando)** in one place.

## Location IDs (important)

Activate exposes two related location identifiers for Pointe Orlando:

| Role | Value | Where it appears |
|---|---|---|
| Site / picker location | **42** · slug `pointe-orlando` | Location picker / site record |
| Scores URL location | **41** · name `orlando (pointe orlando)` | Public `/scores/...` and `/rewards/...` URLs |

Refresh prefers **GET on a friend’s known `scores_url`** (no rebuild/re-encode). GibsonLeader is seeded that way.

Seed player:
- Display name: **GibsonLeader**
- Player slug: `gibsonleader`
- Email: `wesgbrooks@gmail.com`
- Scores: `https://playactivate.com/scores/gibsonleader/41/orlando%20%28pointe%20orlando%29/scores`
- Rewards: `https://playactivate.com/scores/gibsonleader/41/orlando%20%28pointe%20orlando%29/rewards`

## Architecture

One Python service: **FastAPI + Jinja2 + SQLite cache + JSON friends file**.

Supported fields from public Activate pages:
- display name, profile rank, player rank, standing, yearly rank
- total / yearly score, levels beaten, stars, coins
- per-game bests for Hoops, Grid, Hide, Mega Grid, Mega Laser, Control, Strike, Portals, Press, Scan
- rewards: name, cost, stock, location id, status

No private mobile APIs and no auth bypass — only public website pages.

## Quick start (local)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000

Force demo data (no Activate network calls):

```bash
FORCE_DEMO_MODE=true uvicorn app.main:app --port 8000
```

### Docker

```bash
docker build -t activate-orlando-leaderboard .
docker run --rm -p 8000:8000 -e FORCE_DEMO_MODE=true activate-orlando-leaderboard
```

## Adding friends

Seeded Orlando (Pointe Orlando) friends:

| Friend | Binding | Refresh |
|---|---|---|
| **GibsonLeader** | scores URL (`gibsonleader` / location **41**) | GET `scores_url` |
| **TikimanTim** | confirmed scores URL (was handle Tikimantim) | GET `scores_url` |
| **HeavenlyKevinT** | confirmed scores URL | GET `scores_url` |
| **ReyRivera09** | email only — **PENDING Wes** (ambiguous: Amalikite vs yourfriendlyneighborhoodtherapist) | no auto-resolve |

Friends config supports a mix of **scores URLs**, **handles**, and **emails**. Handles/URLs refresh via GET. Emails resolve once via Activate’s public search *unless* `pending_resolution` is set (Rey).

1. Visit https://playactivate.com/scores and look up a player.
2. Open the **Pointe Orlando** scores page (URL location id **41**).
3. Copy the URL and paste it into **Add a friend**, or enter a handle / email.

You can also edit `data/friends.json`. Optional: set `ADMIN_TOKEN` so add/remove/refresh require a shared secret.


## Scoring refresh + caching

- Preferred refresh path: GET the stored public scores URL as-is.
- Optional rewards GET when `FETCH_REWARDS=true`.
- Results cached in SQLite (`CACHE_DB_PATH`) for `CACHE_TTL_SECONDS` (default 10 minutes).
- Requests are rate-limited.
- If Activate/Cloudflare blocks the host, stale cache or demo fixtures are shown.

Optional `ACTIVATE_COOKIE`: paste a browser cookie string into Railway env vars when your deploy IP is challenged. Prefer the paste-URL path over depending on cookies.

## Deploy on Railway (primary)

1. Push this repo to GitHub.
2. In [Railway](https://railway.app): **New Project → Deploy from GitHub repo**.
3. Railway will detect `Dockerfile` / `railway.toml`.
4. Set variables (at least):

| Variable | Example | Notes |
|---|---|---|
| `FORCE_DEMO_MODE` | `false` | `true` until live fetches work |
| `DEMO_MODE_FALLBACK` | `true` | Keep UI usable if Activate blocks |
| `CACHE_TTL_SECONDS` | `600` | 5–15 min recommended |
| `FRIENDS_PATH` | `/app/data/friends.json` | Attach a volume for persistence |
| `CACHE_DB_PATH` | `/app/data/cache.sqlite3` | Same volume |
| `FETCH_REWARDS` | `true` | Also GET public rewards pages |
| `ADMIN_TOKEN` | (secret) | Optional form protection |
| `ACTIVATE_COOKIE` | (optional) | Only if Cloudflare challenges your IP |

5. Generate a public domain (Railway → Settings → Networking).
6. Health check path: `/healthz`.

```bash
npm i -g @railway/cli
railway login
railway init
railway up
railway variables set FORCE_DEMO_MODE=true DEMO_MODE_FALLBACK=true
railway domain
```

## Tests

```bash
pytest -q
```

## License

MIT — see `LICENSE`.
