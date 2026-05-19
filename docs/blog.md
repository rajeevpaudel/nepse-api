# How I reverse engineered the NEPSE website to build a stock price API

Nepal Stock Exchange (NEPSE) has no public API. If you want live stock prices you open their website, navigate to a security, and read a number off a screen. That is the intended experience.

I had a side project that needed stock prices — nothing fancy, just a way to pull the latest traded price for a given ticker without going through a browser. So one evening I opened DevTools and started poking around. What I thought would take an hour ended up taking a few evenings, mostly because NEPSE had more tricks up its sleeve than I expected.

---

## Starting with the network tab

`https://nepalstock.com.np` is a standard Angular SPA. I navigated to a stock page, watched the network tab, and immediately saw the requests I was after:

```
GET /api/nots/security/floorsheet/{id}
```

Simple enough. I copied the URL, ran a curl, and got a `401`. The requests need an `Authorization` header:

```
Authorization: Salter <token>
```

"Salter" is a custom scheme — not Bearer, not Basic. Fine, I just needed to figure out where the token came from.

---

## The token that wasn't what it looked like

Watching the network tab more carefully, I saw the browser hit this first:

```
POST /api/authenticate/prove
```

The response had what looked like standard JWTs:

```json
{
  "accessToken": "eyJhbGciOiJ...<long string>",
  "refreshToken": "eyJhbGciOiJ...<another long string>",
  "salt1": 18,
  "salt2": 34,
  "salt3": 7,
  "salt4": 52,
  "salt5": 29
}
```

I grabbed the `accessToken`, stuck it in the `Authorization: Salter` header, and got another `401`. The raw token from the prove endpoint is not the token that actually works. Something transforms it first, and the five `salt` values are clearly involved.

I went digging through the minified JS bundle, searching for "salt1". Found a function that loaded a WebAssembly module from:

```
https://nepalstock.com.np/assets/prod/css.wasm
```

I saw `.wasm` and my first instinct was to skip it — I assumed it was something CSS related, maybe a CSS-in-JS runtime or a font rendering thing. Completely wrong. The name `css.wasm` is just a red herring. It has nothing to do with stylesheets. It is the authentication engine.

Once I actually downloaded and inspected it, I found five exported functions:

```
cdx(s1, s2, s3, s4, s5) → integer
rdx(s1, s2, s4, s3, s5) → integer   ← s4 and s3 are swapped here
bdx(s1, s2, s4, s3, s5) → integer
ndx(s1, s2, s4, s3, s5) → integer
mdx(s1, s2, s4, s3, s5) → integer
```

Each one takes the five salt values and returns an index. The JS then uses those indices to delete individual characters from the raw token:

```javascript
let i1 = cdx(s1, s2, s3, s4, s5);
let i2 = rdx(s1, s2, s4, s3, s5);
let i3 = bdx(s1, s2, s4, s3, s5);
let i4 = ndx(s1, s2, s4, s3, s5);
let i5 = mdx(s1, s2, s4, s3, s5);

newToken = remove(remove(remove(remove(remove(raw, i1), i2), i3), i4), i5);
```

Five deletions, five characters gone. That shorter string is what actually works in the header. I also noticed the salt argument order is scrambled between functions — `rdx` gets `s4` and `s3` in reverse compared to `cdx`. That feels deliberate, like a small extra trap for anyone trying to reconstruct the logic manually.

Once I understood what was happening, I just ran the same WASM on the server using Python's `wasmtime`:

```python
from wasmtime import Store, Module, Instance

def calculate_tokens(wasm_path, access_token, refresh_token, salts):
    store = Store()
    module = Module.from_file(store.engine, wasm_path)
    instance = Instance(store, module, [])
    exports = instance.exports(store)

    s1, s2, s3, s4, s5 = salts

    def call(fn_name, *args):
        return exports[fn_name](store, *args)

    indices = [
        call("cdx", s1, s2, s3, s4, s5),
        call("rdx", s1, s2, s4, s3, s5),
        call("bdx", s1, s2, s4, s3, s5),
        call("ndx", s1, s2, s4, s3, s5),
        call("mdx", s1, s2, s4, s3, s5),
    ]

    def strip(token, idxs):
        chars = list(token)
        for offset, i in enumerate(idxs):
            del chars[i - offset]
        return "".join(chars)

    return strip(access_token, indices), strip(refresh_token, indices)
```

I cache the file locally and re-download it each morning when the market opens, in case NEPSE ships an update.

---

## SSL errors for no obvious reason

Tokens working, I moved on to actually calling the API from my server. Immediately hit:

```
SSL: CERTIFICATE_VERIFY_FAILED
```

Same request that works fine in the browser, failing with an SSL error from Python. I checked the certificate chain in the browser:

```
nepalstock.com.np
└── GeoTrust TLS RSA CA G1
    └── DigiCert Global Root CA
```

The intermediate cert, `GeoTrust TLS RSA CA G1`, is not in the standard `certifi` bundle that Python ships with. Browsers fetch missing intermediates automatically via the AIA extension in the server certificate. Python does not do that.

I had to bundle it myself — fetch the intermediate from GeoTrust's CA server, convert it from DER to PEM, and concatenate it onto the standard certifi bundle:

```python
import certifi
from cryptography import x509
from cryptography.hazmat.primitives import serialization
import httpx

INTERMEDIATE_URL = "http://cacerts.geotrust.com/GeoTrustTLSRSACAG1.crt"

async def build_ssl_bundle(cache_path):
    async with httpx.AsyncClient() as client:
        resp = await client.get(INTERMEDIATE_URL)

    # GeoTrust serves it as DER-encoded binary; convert to PEM
    cert = x509.load_der_x509_certificate(resp.content)
    intermediate_pem = cert.public_bytes(serialization.Encoding.PEM).decode()

    with open(certifi.where()) as f:
        standard_bundle = f.read()

    bundle = standard_bundle + "\n" + intermediate_pem
    cache_path.write_text(bundle)
    return str(cache_path)
```

Then I passed the path as `verify` to every client that talks to NEPSE:

```python
ssl_bundle = await get_ssl_bundle()
async with httpx.AsyncClient(verify=ssl_bundle) as client:
    resp = await client.get(SECURITIES_URL, headers={"Authorization": f"Salter {token}"})
```

---

## One more thing: the request ID I nearly missed entirely

I thought I was done at this point. Got tokens working, SSL sorted, started getting 200 responses. I was so confident I had cracked it that I built another small project on top of this API the same night.

The next day it stopped working. Not with an error — still 200, just completely empty response data. I assumed something had expired and spent a while refreshing tokens, rebuilding the SSL bundle, double-checking the auth header. Everything looked right. Still empty.

That was the first clue: it had worked yesterday and stopped today. Something was changing daily.

I downloaded the compiled `main.js` from the browser — the full production bundle, minified, about as readable as you'd expect. I started searching for anything time-related. The keyword `day` showed up in 165 places. I went through them one by one, which was not fun. Most were irrelevant. But eventually I found one that looked different from the rest:

```javascript
var e = this.utilsService.getDummyData()[this.dummyId] + this.dummyId + 2 * this.day;
```

And that exact expression was repeated in multiple places. So `getDummyData()` is a list, `dummyId` indexes into it, and `day` is the current day-of-month. I found `getDummyData()` — it just returns a hardcoded 100-element array of integers:

```javascript
const _DATA = [147, 117, 239, 143, 157, 312, 161, 612, 512, 804, ...];
```

Now I needed to know where `dummyId` came from. There was only one place in the whole bundle where it was assigned:

```javascript
getMarketStatus() {
    this.dashboardService.getMarketStatus().then(t => {
        this.marketStatus = t,
        this.date = new Date(t.asOf),
        this.dummyId = t.id,
        this.getData()
    })
}
```

`t.id` — so it comes from a market status API response. I went back through my network tab recordings and found it: there was an endpoint the browser always hit on page load that I had ignored:

```
GET https://nepalstock.com.np/api/nots/nepse-data/market-open
```

Response:

```json
{"isOpen": "OPEN", "asOf": "2026-05-08T15:00:00", "id": 80}
```

That `id` field is the `dummyId`. It changes every day. Once I had it, the calculation was straightforward:

```python
id_to_send = _DATA[market_open_id] + market_open_id + 2 * today.day
```

And that value goes into the request body as `id`. Without it, NEPSE returns 200 with an empty payload and gives you nothing to debug with.

```python
_cache: dict = {}

def get_id(market_open_id: int) -> int:
    today = date.today()
    key = (today, market_open_id)
    if key not in _cache:
        _cache[key] = _DATA[market_open_id] + market_open_id + 2 * today.day
    return _cache[key]
```

---

## The full flow, end to end

Once all three were sorted, a price lookup goes like this:

```
1. GET css.wasm from CDN (cached locally)
2. POST /api/authenticate/prove  →  raw tokens + salts
3. Execute css.wasm cdx/rdx/bdx/ndx/mdx with salts  →  5 indices
4. Delete characters at those indices from tokens  →  valid tokens
5. Bundle GeoTrust intermediate CA with certifi  →  custom SSL context
6. GET /api/nots/nepse-data/market-open  →  market session id
7. id = _DATA[market_open_id] + market_open_id + 2 * today.day
8. GET /api/nots/security/floorsheet/{nepse_id}
       Authorization: Salter <transformed_access_token>
       id: <calculated>
   →  last traded price
```

Tokens are cached in a PostgreSQL table with a 120-second TTL. The WASM and SSL bundle live on disk and get purged each market close, re-fetched on market open.

---

## What I ended up with

```bash
curl -H "X-API-Key: secret" http://localhost:8000/securities/NABIL/price
```

```json
{
  "symbol": "NABIL",
  "name": "Nabil Bank Limited",
  "last_traded_price": 1243.5
}
```

Two scheduled jobs handle the lifecycle: one at 10:00 NST to download fresh WASM and refresh tokens, one at 15:01 NST to clear the cache. Everything else — token expiry, SSL bundling, request ID calculation — is handled transparently on each request.

Full source is on GitHub. See [architecture.md](architecture.md) for a component-by-component breakdown.

---

## What I learned

The `css.wasm` thing genuinely fooled me for a bit. My instinct was to ignore it because of the name, and that cost me probably half an hour of going down the wrong path. Good lesson about not pattern-matching on filenames when reading unfamiliar code.

The SSL thing is one of those problems that looks mysterious until you understand it, then seems obvious in retrospect. Browsers have been doing AIA fetching silently for years, so most developers never think about it. The moment you move a request out of a browser and into server-side code, that invisible behavior disappears and you're left with a confusing error message.

The payload ID was the most annoying part because NEPSE gives you no signal that it's missing — just empty results. If you're poking at an API and getting suspiciously empty responses despite valid auth, check whether there's a hidden required field.

NEPSE is clearly trying to make this harder, and I get it. This project is for personal use, accesses data at a low rate, and doesn't redistribute anything. If you use it yourself, check NEPSE's terms of service first.
