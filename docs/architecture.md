# Architecture

## Overview

nepse-api is a FastAPI service that acts as a proxy between clients and NEPSE's internal data APIs. Because NEPSE's APIs require client-side authentication that is intentionally obfuscated, the service replicates that authentication server-side before forwarding requests.

```
Client
  │  X-API-Key header
  ▼
FastAPI app (main.py)
  │
  ├── /securities          →  DB query (SQLAlchemy + PostgreSQL/SQLite)
  ├── /securities/sync     →  scraper/securities.py  →  NEPSE API
  ├── /securities/{}/price →  scraper/prices.py      →  NEPSE API
  └── /debug/run-market-open → services/scheduler.py
                                   │
                          ┌────────┴────────┐
                          ▼                 ▼
                  scraper/auth.py    scraper/wasm_loader.py
                  scraper/ssl_bundle.py
```

---

## Components

### `main.py` — Application entry point

Initialises the FastAPI app, registers routers, runs `init_db` on startup to create tables if they don't exist. The scheduler (`services/scheduler.py`) is instantiated here and can be wired into the lifespan context.

### `auth.py` — API key gate

A FastAPI dependency that reads `X-API-Key` from the request header and compares it to the `API_KEY` env variable. Returns `403` on mismatch.

### `scraper/ssl_bundle.py` — Custom SSL certificate

NEPSE's TLS chain includes `GeoTrust TLS RSA CA G1`, an intermediate CA that is not present in the standard `certifi` bundle. At first use:

1. Fetch the DER-encoded intermediate cert from `cacerts.geotrust.com`.
2. Convert DER → PEM using `cryptography`.
3. Concatenate with the system `certifi` bundle and write to `CACHE_DIR/nepalstock_ssl/bundle.pem`.

All `httpx` clients that talk to NEPSE are initialised with `verify=<path to bundle>`.

### `scraper/wasm_loader.py` — WASM execution

NEPSE ships a WebAssembly module (`css.wasm`) that is used by its web app to transform authentication tokens. We:

1. Download `css.wasm` from NEPSE's CDN and cache it at `CACHE_DIR/css.wasm`.
2. Load it with `wasmtime` at token-calculation time.
3. Export five functions (`cdx`, `rdx`, `bdx`, `ndx`, `mdx`) and call them with the five salt values that NEPSE provides per authentication session.

Each function returns an integer index. The token transformation removes one character per index from the raw token string, reducing its length by five characters total.

### `scraper/auth.py` — Token acquisition and caching

```
calc_new_tokens()
  1. POST /api/authenticate/prove  →  raw access_token, refresh_token, salt1–5
  2. Load css.wasm, compute 5 indices for each token
  3. Strip characters at those indices
  4. Return (access_token, refresh_token)

get_or_refresh_tokens(session, force=False)
  - Load NepseToken row from DB
  - If age < 120s and not forced → return cached tokens
  - Otherwise → calc_new_tokens(), persist to DB, return fresh tokens
```

The `NepseToken` table holds exactly one row at all times (old row deleted before inserting new one).

### `scraper/payload_calc.py` — Daily request ID

Price requests require an `id` field in the body that changes daily. It is derived from:

- A static 100-element lookup table (`_DATA`) extracted from NEPSE's bundled JavaScript.
- The `id` field returned by `GET /api/nots/nepse-data/market-open` (a value 0–99).
- The current calendar day-of-month.

```python
id_to_send = _DATA[market_open_id] + market_open_id + 2 * today_day
```

The result is cached in memory per day. Without this field in the request body, NEPSE returns 200 with an empty payload and no error.

### `scraper/securities.py` — Securities sync

Calls `GET /api/nots/security?nonDelisted=true` with the auth token. Iterates the response and upserts into the `securities` table: updates existing rows by `nepse_id`, inserts new ones. Returns the total count.

### `scraper/prices.py` — Live price fetch

Calls NEPSE's price endpoint with the computed `payloadId` and auth token. Returns the `lastTradedPrice` float or `None` if NEPSE returns empty data.

### `services/scheduler.py` — Background jobs

Two APScheduler cron jobs keyed to Nepal time (Asia/Kathmandu):

**Market open (Mon–Fri 10:00 NST)**
- `clear_cache()` — deletes cached WASM and SSL bundle so stale files are not reused.
- `download_wasm_file()` — fetches fresh `css.wasm`.
- `calc_new_tokens()` — computes and persists fresh tokens.

**Market close (Mon–Fri 15:01 NST)**
- `clear_cache()` — removes cached files so they are refetched on next market open.

---

## Database schema

### `securities`

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| nepse_id | Integer UNIQUE | NEPSE's internal security ID |
| symbol | String UNIQUE | Ticker, e.g. `NABIL` |
| name | String | Full company name |
| is_active | Boolean | `False` for delisted securities |
| updated_at | DateTime(UTC) | Last sync timestamp |

### `nepse_token`

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | Always one row |
| access_token | String | Transformed access token |
| refresh_token | String | Transformed refresh token |
| fetched_at | DateTime(UTC) | Used to determine staleness (TTL = 120s) |

---

## Token lifecycle

```
Market open (10:00 NST)
  └── calc_new_tokens() → stored in DB

Price request arrives
  └── get_or_refresh_tokens()
        ├── age < 120s → use cached
        └── age >= 120s → calc_new_tokens() → update DB → use fresh

3 retries fail
  └── force=True → calc_new_tokens() regardless of age

Market close (15:01 NST)
  └── clear_cache() — WASM and SSL bundle purged
```

---

## Caching strategy

| Resource | Cache location | Invalidated |
|---|---|---|
| `css.wasm` | `CACHE_DIR/css.wasm` | Market open/close jobs, or on startup if absent |
| SSL bundle | `CACHE_DIR/nepalstock_ssl/bundle.pem` | Market open/close jobs |
| Payload ID | In-memory (module-level variable) | Recomputed when calendar day changes |
| NEPSE tokens | `nepse_token` DB table | Age > 120s, or forced refresh |

---

## Deployment

The service runs as a single Docker container (no worker processes needed — all concurrency is async). A PostgreSQL container is not included in `docker-compose.yml` by default; point `DATABASE_URL` at an external instance or use `sqlite+aiosqlite:///nepse.db` for lightweight deployments.

Memory ceiling is set to 400 MB in `docker-compose.yml`. Typical idle usage is ~80–120 MB.
