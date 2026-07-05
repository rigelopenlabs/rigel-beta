# rigel-beta

A "TestFlight for Rigel desktop apps". Users subscribe (by email) to in-development
apps and receive a notification email whenever a new version ships. Built for the
NOCBoard family but generic for any Rigel desktop app.

**Stack:** Python 3.13 + FastAPI + SQLite + [Resend](https://resend.com) (HTTP API) + Jinja2.
No Postgres. Host port **9486** -> internal uvicorn **8000**.

## How it works

1. A visitor picks one or more apps on the landing page and submits their email.
2. They get a **double opt-in** email with a single confirm link covering all the apps
   they selected (`/confirm/{token}`). Subscriptions stay `pending` until confirmed.
> **One-shot release:** `publish-release.sh` publishes a DMG to its channel and
> then announces it — see "Publishing a release" below. `notify-beta.sh` is the
> announce-only step it calls.

3. When you publish a new release (via `POST /api/releases` or `notify-beta.sh`),
   every **confirmed** subscriber of that app gets a "new version available" email
   with a download link and a personal unsubscribe link (`/unsubscribe/{token}`).

Tokens are unguessable UUIDs (one per subscription).

## Endpoints

### Public
| Method | Path | Description |
|--------|------|-------------|
| GET  | `/` | Landing page (dark theme, cyan accent): lists apps + subscription form. |
| POST | `/subscribe` | Form `email` + repeated `app_keys`. Upserts subscriber, creates `pending` subscriptions, sends the double opt-in email. |
| GET  | `/confirm/{token}` | Confirms the matching subscription and all other pending ones for that subscriber. Success page. |
| GET  | `/unsubscribe/{token}` | Marks that subscription `unsubscribed`. Confirmation page. |
| GET  | `/health` | `{"ok": true}`. |

### Admin (header `X-API-Key` must equal `BETA_ADMIN_KEY`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/apps` | Upsert an app (idempotent by `key`). |
| GET  | `/api/apps` | List all apps. |
| POST | `/api/releases` | Insert a release, bump `apps.latest_version`/`download_url`, email all confirmed subscribers. Returns `{sent, recipients, release}`. |
| GET  | `/api/subscribers?app=<key>` | List subscriptions (email/status/token) for an app. |

`POST /api/apps` body:
```json
{"key":"nocboard-wl","name":"NOCBoard WL","description":"...","download_url":"https://...","latest_version":"3.3.3","icon_emoji":"📡","is_public":false}
```

`POST /api/releases` body (`download_url`/`notes` optional; empty `download_url` keeps the app's current one):
```json
{"app_key":"nocboard-energia","version":"3.5.0","download_url":"https://.../NOCBoard-Energia-latest.dmg","notes":"Fix crash"}
```

## Data model (SQLite)

- **apps**: `key` (PK), name, description, download_url, latest_version, icon_emoji, is_public, created_at
- **subscribers**: id, email (unique), created_at
- **subscriptions**: id, subscriber_id (FK), app_key (FK), status (`pending`/`confirmed`/`unsubscribed`), token (uuid, unique), confirmed_at, created_at — unique per (subscriber, app)
- **releases**: id, app_key, version, download_url, notes, published_at

## Config (env vars, dev defaults)

| Var | Default | Notes |
|-----|---------|-------|
| `BETA_DB_PATH` | `./rigel-beta.db` | SQLite file path. |
| `RESEND_API_KEY` | *(empty)* | **Empty => DEV mode: no network, emails are printed, send returns ok.** |
| `BETA_FROM` | `Rigel Beta <beta@vivesincables.com>` | Resend `from`. Must be a verified domain in prod. |
| `BETA_ADMIN_KEY` | `dev-admin-key` | Admin API key. **Change in prod.** |
| `BASE_URL` | `http://localhost:9486` | Used to build confirm/unsubscribe links in emails. |

## Run locally

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt

# tests (run in DEV email mode, no creds needed)
.venv/bin/pytest -q

# seed runs automatically on startup; or run it standalone:
.venv/bin/python seed.py

# start the server (DEV mode: no RESEND_API_KEY -> emails are printed to the log)
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 9486
```

Open http://localhost:9486 . Subscribe, watch the log for `[beta-email DEV] ...`,
copy the confirm token from `/api/subscribers?app=...`, then hit `/confirm/{token}`.

### notify-beta.sh

Helper to publish a release from a build pipeline:

```bash
# contract: notify-beta.sh <app_key> <version> <download_url> [notes]
export BETA_API_URL=http://localhost:9486        # default
export BETA_ADMIN_KEY=dev-admin-key              # must match server

./notify-beta.sh nocboard-energia 3.5.0 \
  https://releases.vivesincables.com/dl/nocboard/NOCBoard-Energia-latest.dmg \
  "Fix crash en arranque"
# -> {"sent":2,...}
#    sent: 2 (recipients: 2)
```

## Resend setup (production email)

1. Create an account at https://resend.com.
2. **Verify your sending domain** (`vivesincables.com`): add the DKIM/SPF/DMARC DNS
   records Resend gives you. Until verified you can only send from `onboarding@resend.dev`.
3. Create an API key (Resend dashboard -> API Keys).
4. Set `RESEND_API_KEY` and a `BETA_FROM` on the verified domain (e.g.
   `Rigel Beta <beta@vivesincables.com>`). With the key set, the service makes real
   HTTP calls to `https://api.resend.com/emails`. Without it, it stays in DEV mode.

## Deploy on Dokploy (dp01)

1. Push this repo to GitHub (e.g. an org under `rigelopenlabs`/`mesquitetech`).
2. In Dokploy create a **Compose** service pointing at the repo; it uses
   `docker-compose.yml` (build `Dockerfile.prod`). The SQLite DB persists on the
   `rigel_beta_data` volume mounted at `/data`.
3. Set env in Dokploy: `RESEND_API_KEY`, `BETA_ADMIN_KEY` (strong!), `BETA_FROM`,
   and `BASE_URL` = the public URL (e.g. `https://beta.vivesincables.com`).
4. dp01 is behind double NAT; expose publicly via **Pangolin** (skill
   `pangolin-expose`) pointing a `*.vivesincables.com` subdomain at host port `9486`.
5. Confirm `https://<your-domain>/health` returns `{"ok": true}`.

## Tests

`pytest` drives the full flow with FastAPI `TestClient` in DEV email mode
(no credentials/network): landing 200, subscribe -> confirm -> release (sends in
DEV mode) -> unsubscribe, plus that all `/api/*` endpoints reject a missing/wrong
`X-API-Key`, and app upsert idempotency.

## Publishing a release (`publish-release.sh`)

One command: publish the notarized DMG (built by the app's `build-dmg.sh`) to its
channel, then announce it to beta subscribers. The announce fires **after** the
download URL is live (never before), so testers never get a stale link.

**Public app** (served from `releases.vivesincables.com`, e.g. NOCBoard Energía/Datos, DoctorNet, Atlas):

```bash
NOTARIZE=1 ~/developer/NOCBoard-Energia/build-dmg.sh          # build first
./publish-release.sh --mode public \
    --repo ~/developer/NOCBoard-Energia \
    --beta-key nocboard-energia \
    --subdir nocboard \
    --replace NOCBoard-Energia-v3.9.6.dmg \
    --notes "Fixes from the field test"
```

It copies `dist/<name>-vX.Y.Z.dmg` + `<name>-latest.dmg` into
`rigel-releases/dl/<subdir>/`, commits + pushes, triggers the Dokploy deploy (if
`RIGEL_DEPLOY_HOOK` is set — otherwise trigger it in Dokploy/MCP), polls the public
`-latest` URL until it serves the new build (sha match), then runs `notify-beta.sh`.

**Drive-only app** (access-controlled, e.g. NOCBoard WL/CX/CX-Datos):

```bash
./publish-release.sh --mode drive \
    --repo ~/developer/NOCBoard \
    --beta-key nocboard-wl \
    --download-url "https://drive.google.com/…" \
    --replace NOCBoard-v3.7.2.dmg
```

Env: `RIGEL_DEPLOY_HOOK` (Dokploy compose webhook, optional), `BETA_ADMIN_KEY`
(required for a real notify), `BETA_API_URL` (default prod), `SKIP_NOTIFY=1`
(publish only). Use `--dry-run` to preview. Real emails only send once the server
has a `RESEND_API_KEY`; otherwise the notify is logged server-side (DEV mode).
