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

