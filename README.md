# nepse-api

A self-hosted REST API for live Nepal Stock Exchange (NEPSE) data, built by reverse engineering the NEPSE website's client-side authentication.

NEPSE's web app protects its data APIs behind an obfuscated authentication system: WASM-based token manipulation, a custom SSL certificate chain, and a daily payload ID scheme. This project replicates that mechanism server-side so you can query stock prices programmatically.

Read the full reverse engineering writeup in [`docs/blog.md`](docs/blog.md).

---

## Features

- Live stock prices for any listed security
- Full securities list
- Auto-refreshing tokens (market-open scheduler)
- API key authentication

---

## Quickstart

### Docker (recommended)

Docker Compose starts both the API and a PostgreSQL database.

```bash
cp .env.example .env
# edit .env — set POSTGRES_PASSWORD and API_KEY at minimum
```

```bash
docker-compose up --build
```

The API is available at `http://localhost:8000`.

Data is persisted in a named Docker volume (`db_data`). To wipe it:

```bash
docker-compose down -v
```

### Local

Requires a running PostgreSQL instance (or use SQLite for quick testing).

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

```bash
export DATABASE_URL="sqlite+aiosqlite:///nepse.db"   # or a postgres URL
export API_KEY="your-secret-key"

uvicorn main:app --reload
```

---

## Environment variables

When using Docker Compose, `DATABASE_URL` is constructed automatically from the Postgres variables — you only need to set it when connecting to an external database.

| Variable | Required | Default | Description |
|---|---|---|---|
| `POSTGRES_PASSWORD` | Yes (compose) | — | Password for the bundled PostgreSQL service |
| `POSTGRES_USER` | No | `nepse` | PostgreSQL username |
| `POSTGRES_DB` | No | `nepse_db` | PostgreSQL database name |
| `API_KEY` | Yes | — | Value clients must send in `X-API-Key` header |
| `DATABASE_URL` | External DB only | — | SQLAlchemy async URL (`postgresql+asyncpg://…` or `sqlite+aiosqlite:///…`) |
| `CACHE_DIR` | No | `.cache` | Directory for WASM and SSL certificate cache |
| `DEBUG_MODE` | No | `false` | Enables `/debug/*` endpoints |

---

## API reference

All endpoints (except `/health`) require the header `X-API-Key: <your key>`.

### `GET /health`

```json
{"status": "ok", "debug_mode": false}
```

### `GET /securities?page=1&page_size=50`

Returns paginated list of active securities.

```json
[
  {"nepse_id": 123, "symbol": "NABIL", "name": "Nabil Bank Limited"},
  ...
]
```

### `GET /securities/search?q=nabil`

Search active securities by symbol or name (case-insensitive, returns up to 20 results).

```json
[
  {"nepse_id": 123, "symbol": "NABIL", "name": "Nabil Bank Limited"}
]
```

### `POST /securities/sync`

Pulls the latest securities list from NEPSE and upserts into the database.

```json
{"status": "done", "synced": 248}
```

### `GET /securities/{symbol}/price`

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/securities/NABIL/price
```

```json
{"symbol": "NABIL", "name": "Nabil Bank Limited", "last_traded_price": 1243.5}
```

Returns `404` if the symbol is not found, `503` if NEPSE returns no price data.

### `POST /debug/run-market-open` _(DEBUG_MODE only)_

Manually triggers the market-open job: clears cache, downloads fresh WASM, refreshes tokens.

---

## How it works

See [`docs/architecture.md`](docs/architecture.md) for the technical overview and [`docs/blog.md`](docs/blog.md) for the full reverse engineering story.

NEPSE sends raw tokens alongside 5 salt values. Its own `css.wasm` computes indices where characters must be deleted from those tokens — we download and run that same WASM locally. The site also uses an intermediate CA (`GeoTrust TLS RSA CA G1`) absent from standard certificate stores, so we fetch and bundle it at startup. Price requests additionally require a daily payload ID derived from a lookup table baked into NEPSE's JS, combined with today's day-of-month and a market-session ID.

---

## Project structure

```
nepse-api/
├── main.py              # FastAPI app, lifespan, middleware
├── auth.py              # API key enforcement
├── config.py            # Settings from env
├── scraper/
│   ├── wasm_loader.py   # Download and execute css.wasm
│   ├── ssl_bundle.py    # Build custom SSL cert bundle
│   ├── auth.py          # Acquire and cache NEPSE tokens
│   ├── payload_calc.py  # Daily payload ID calculation
│   ├── securities.py    # Sync securities from NEPSE API
│   └── prices.py        # Fetch live price for a security
├── routers/
│   ├── securities.py    # /securities endpoints
│   └── debug.py         # /debug endpoints
├── services/
│   └── scheduler.py     # APScheduler market-open/close jobs
├── db/
│   ├── models.py        # Security, NepseToken ORM models
│   ├── database.py      # Async engine and session factory
│   └── init_db.py       # Schema creation
└── tests/               # pytest suite, all components mocked
```

---

## Scheduler

Two APScheduler jobs run on Nepal time (NST, UTC+5:45):

| Job | Schedule | Actions |
|---|---|---|
| Market open | Mon–Fri 10:00 | Clear cache, download WASM, refresh tokens |
| Market close | Mon–Fri 15:01 | Clear cache |

Tokens are also refreshed on-demand if they are older than 120 seconds.

---

## Running tests

```bash
pytest
```

Tests use an in-memory SQLite database and mock all external HTTP calls to NEPSE.

---

## Limitations

- NEPSE does not provide an official public API; this project may break if NEPSE changes its authentication scheme.
- Price data reflects the last traded price, not real-time tick data.
- The `css.wasm` file and intermediate CA are fetched from NEPSE's servers at runtime. If those URLs change, update `scraper/wasm_loader.py` and `scraper/ssl_bundle.py`.

---
