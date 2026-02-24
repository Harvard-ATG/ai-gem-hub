# Gem Hub

A Flask app that serves as a homepage for Gemini Gems. Users can browse gems by category, save favorites, and submit new bot requests for admin approval.

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv run python app.py
```

Open [http://localhost:5000](http://localhost:5000).

## Docker

```bash
docker compose up --build
```

Open [http://localhost:5000](http://localhost:5000).

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `LOG_LEVEL` | Logging level (e.g. `DEBUG`, `INFO`). | `INFO` |
| `TRUSTED_HOSTS` | Allowed hostnames for incoming requests (comma-separated). Include `:port` if it’s not the default. | `localhost:5000,127.0.0.1:5000` |
| `SECRET_KEY` | Flask session signing key. Set to a random value in production. | `dev-secret-key-change-me` |
| `MAGIC_LINK_TOKEN` | Shared token for magic link auth. When unset, the app runs in open access mode. | _(empty — open access)_ |

## Authentication

The app supports optional magic link authentication for sharing with reviewers without a VPN or password dialog.

**How it works:** When `MAGIC_LINK_TOKEN` is set, all routes are gated behind a session cookie. Visitors see an "access required" page until they open the magic link URL, which sets a 30-day cookie and redirects to the homepage.

**Magic link URL format:** `https://<host>/auth/<MAGIC_LINK_TOKEN>`

**Generating production values:**

```bash
# MAGIC_LINK_TOKEN:
python3 -c "import uuid; print(uuid.uuid4())"

# SECRET_KEY:
python3 -c "import secrets; print(secrets.token_hex(32))"
```

**Revoking access:** Rotate `SECRET_KEY` to invalidate all existing sessions.

