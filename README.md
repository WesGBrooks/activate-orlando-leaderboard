# Activate Orlando Friends Leaderboard

A tiny FastAPI app so Wes and friends can compare [Activate](https://playactivate.com) scores for **Orlando (Pointe Orlando)** in one place.

Public site focus:
- Location id **42**, slug **`pointe-orlando`**
- Data source: the same public `/scores` pages a browser uses on [playactivate.com/scores](https://playactivate.com/scores)
- No private mobile APIs, no auth bypass

## Architecture (short)

One Python service: **FastAPI + Jinja2 + SQLite cache + JSON friends file**. Friends are ranked by Orlando location total score. The preferred way to bind a player is pasting their public scores URL (or player id) after looking them up once on Activate. Optional email search is implemented with CSRF/session bootstrap, but Cloudflare often blocks datacenter IPs — when live fetches fail, the app falls back to cached or demo fixture data so the UI still works.

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

1. Visit https://playactivate.com/scores and search your player name/email.
2. Open the **Pointe Orlando** player page.
3. Copy the URL (shape: `/scores/{player}/{scoreLocation}/pointe-orlando/scores`).
4. In this app, use **Add a friend** and paste that URL (or just the `{player}` id).

You can also edit `data/friends.json` directly. Wes is seeded with email `wesgbrooks@gmail.com` as a placeholder until a scores URL/player id is pasted.

Optional: set `ADMIN_TOKEN` so add/remove/refresh require a shared secret.

## Scoring refresh + caching

- Scores are fetched from public Activate pages with a project User-Agent.
- Results are cached in SQLite (`CACHE_DB_PATH`) for `CACHE_TTL_SECONDS` (default 10 minutes).
- Requests are rate-limited (~1.25s apart).
- If Activate/Cloudflare blocks the host, stale cache or demo fixtures are shown.

Optional `ACTIVATE_COOKIE`: paste a browser cookie string (including `cf_clearance` if needed) into Railway env vars when your deploy IP is challenged. Prefer the paste-URL path over depending on cookies.

## Deploy on Railway (primary)

Cost: Railway hobby/trial is plenty for a private friends board (often free credits / a few dollars).

1. Push this repo to GitHub.
2. In [Railway](https://railway.app): **New Project → Deploy from GitHub repo**.
3. Railway will detect `Dockerfile` / `railway.toml`.
4. Set variables (Dashboard → Variables), at least:

| Variable | Example | Notes |
|---|---|---|
| `FORCE_DEMO_MODE` | `false` | `true` until friends have scores URLs |
| `DEMO_MODE_FALLBACK` | `true` | Keep UI usable if Activate blocks |
| `CACHE_TTL_SECONDS` | `600` | 5–15 min recommended |
| `FRIENDS_PATH` | `/app/data/friends.json` | Attach a volume for persistence |
| `CACHE_DB_PATH` | `/app/data/cache.sqlite3` | Same volume |
| `ADMIN_TOKEN` | (secret) | Optional form protection |
| `ACTIVATE_COOKIE` | (optional) | Only if Cloudflare challenges your IP |
| `HTTP_USER_AGENT` | see `.env.example` | Identifies this open-source app |

5. Generate a public domain (Railway → Settings → Networking).
6. Health check path: `/healthz`.

CLI alternative:

```bash
npm i -g @railway/cli   # or: brew install railway
railway login
railway init
railway up
railway variables set FORCE_DEMO_MODE=true DEMO_MODE_FALLBACK=true
railway domain
```

### One-click style

If the repo is public on GitHub:

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/new/template?template=https://github.com/WesGBrooks/activate-orlando-leaderboard)

(You can also create an empty Railway project and point it at this repo’s Dockerfile.)

## Tests

```bash
pytest -q
```

## License

MIT — see `LICENSE`.

## Also possible

The same Dockerfile can run on AWS App Runner (or a Lambda Function URL with an adapter). Railway is the supported path for this project so maintainers don’t need AWS CLI/IAM setup.
