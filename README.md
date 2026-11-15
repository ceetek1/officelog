# Attendance (MVP)

Workers clock in and out by scanning a code on the entrance TV with their phone, confirmed with
Face ID. The manager and the MD see the day, decide on reasons for lateness or absence, and the MD
sees how much the system is actually used.

- What to build: [`docs/attendance-mvp-spec.md`](docs/attendance-mvp-spec.md)
- Where the build differs from the spec, and why: [`docs/decisions.md`](docs/decisions.md)
- Deploying: [`docs/deploy-railway.md`](docs/deploy-railway.md)

**Status:** Steps 1–5 of 6. Done: database, admin commands, MD sign-in, the entrance TV, invites
with Face ID, clocking in and out with receipts, the attendance rules, Today, History, the
manager's Team today, reasons, approvals, the MD's override, the activity log, People (add a
worker, reset a lost phone, deactivate), TV setup and removal, and time from the paper sheet.
Next: the MD's Today board, history per person, Usage, and the privacy notice page (Step 6).

Pages: `/` phone app (manager: `/team`, `/approvals`, `/people`, `/people/tv`) ·
`/invite/<token>` new phone · `/tv` entrance TV (`/tv/pair/<code>` sets it up) · `/md/login` MD
(`/md`, `/md/approvals`, `/md/activity`).

Phones need **HTTPS** for the camera and Face ID, so real-phone testing happens on the Railway
site (or another HTTPS address), not on `http://localhost` from another device.

## Layout

| Path | What |
|---|---|
| `app/` | FastAPI backend. `app/rules/` holds the pure attendance rules (no database or framework). |
| `migrations/` | Alembic database migrations |
| `frontend/` | React + TypeScript + Vite app (phones, MD web, entrance TV) |
| `tests/` | pytest tests (they need a Postgres server) |

## Run it on your computer

You need Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 22 or newer, and Postgres 16.

With Docker, one command starts both the database and the app at <http://localhost:8000>:

```bash
docker compose up --build
```

Without Docker:

```bash
cp .env.example .env
```

Edit `.env` so `DATABASE_URL` points at your Postgres, then:

```bash
uv sync
```

```bash
(cd frontend && npm ci && npm run build)
```

```bash
uv run python -m app.admin migrate
```

```bash
uv run python -m app.admin create-md --name "Your Name" --email you@example.com
```

```bash
uv run uvicorn app.main:app --port 8000
```

Open <http://localhost:8000/md/login>. For frontend work with hot reload, also run
`npm run dev` in `frontend/` and open <http://localhost:5173>.

## Tests

The tests create (and drop) a database called `officelog_test` on the Postgres server you give
them:

```bash
TEST_DATABASE_ADMIN_URL=postgresql://postgres@localhost:5432/postgres uv run pytest
```

```bash
(cd frontend && npm test && npm run build)
```

## Admin commands

```bash
uv run python -m app.admin --help
```

| Command | What it does |
|---|---|
| `migrate` | Updates the database and the app's restricted database user. Runs on every container start. |
| `create-md --name --email` | Creates the MD (asks for a password). |
| `reset-md-password --email` | Sets a new password for the MD. |
| `create-manager --name` | Creates the manager and prints their one-time invite link. |
| `create-worker --name` | Creates a worker and prints their one-time invite link (the manager normally uses People). |
| `reset-phone --name` | Revokes a person's phone and sessions and prints a new invite link. For the manager's own lost phone. |
| `create-tv-link` | Prints a one-time TV setup link and code (the manager normally uses People → Entrance TV). |

## Environment variables

See [`.env.example`](.env.example) for the full list with explanations.
