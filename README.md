# Attendance (MVP)

Workers clock in and out by scanning a code on the entrance TV with their phone, confirmed with
Face ID. The manager and the MD see the day, decide on reasons for lateness or absence, and the MD
sees how much the system is actually used.

- What to build: [`docs/attendance-mvp-spec.md`](docs/attendance-mvp-spec.md)
- Where the build differs from the spec, and why: [`docs/decisions.md`](docs/decisions.md)
- Deploying: [`docs/deploy-railway.md`](docs/deploy-railway.md)

**Status:** all 6 build steps of the MVP are done, waiting for the owner's checks on real phones.
Built: database, admin commands, MD sign-in, the entrance TV, invites with Face ID, clocking in and
out with receipts, the attendance rules, Today, History, the manager's Team today, reasons,
approvals, the MD's override, the activity log, People (add a worker, reset a lost phone,
deactivate), TV setup and removal, time from the paper sheet, the MD's Today board, history per
person, the Usage numbers (page and command) and the privacy notice.

## Pages

| Address | Who | What |
|---|---|---|
| `/` | workers, manager | Today (the big Clock In / Clock Out button); workers also get History and Reasons |
| `/team`, `/approvals`, `/people`, `/people/tv` | manager | Team today (+ time from paper), approvals, People, Entrance TV |
| `/invite/<token>` | a new phone | privacy notice, then Face ID setup |
| `/tv` | the entrance TV | the rotating code; when not set up, asks for the setup code |
| `/md/login` | MD | email + password sign-in |
| `/md`, `/md/people`, `/md/people/<id>`, `/md/approvals`, `/md/activity`, `/md/usage` | MD | Today board (any day), people and their history, approvals and override, activity log, usage numbers |
| `/privacy` | anyone | the privacy notice (Nigeria Data Protection Act 2023) |

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
| `create-manager --name` | Creates the manager and prints their one-time invite link. The MD can do the same without a shell: MD → People → **Add Manager**. |
| `create-worker --name` | Creates a worker and prints their one-time invite link (the manager normally uses People). |
| `reset-phone --name` | Revokes a person's phone and sessions and prints a new invite link. For the manager's own lost phone. |
| `create-tv-link` | Prints a one-time TV setup link and code (the manager normally uses People → Entrance TV). |
| `usage [--from YYYY-MM-DD] [--to YYYY-MM-DD]` | Prints the usage numbers per working day and in total, the same as the MD's Usage page. Default: the last 14 days. |

On Railway, run these in the app service's shell (see [`docs/deploy-railway.md`](docs/deploy-railway.md)).

## Environment variables

Set them in `.env` locally, or as service variables on Railway. [`.env.example`](.env.example) has
the same list with comments.

| Variable | Needed | What it is |
|---|---|---|
| `DATABASE_URL` | yes | The database owner's address. Used to update the database and to create the app's restricted user. |
| `APP_DB_ROLE` | no (`attendance_app`) | The restricted database user the app runs as. It can't change recorded times or the activity log. |
| `APP_DB_PASSWORD` | yes | That user's password: a long random string. |
| `MASTER_SECRET` | yes | Makes the TV's rotating codes. At least 32 random characters; keep it secret. |
| `BASE_URL` | yes | The site's public address, no trailing slash. Face ID passkeys belong to it: set it before anyone registers. |
| `COOKIE_SECURE` | yes on Railway (`true`) | `false` only for `http://localhost`. |
| `COMPANY_NAME` | no | Shown on the sign-in screen and in the privacy notice. |
| `PRIVACY_CONTACT` | recommended | Who to contact about personal data, shown in the privacy notice. |
| `TIMEZONE` | no (`Africa/Lagos`) | The company's timezone. |
| `SCHEDULE_JSON` | no | Start, grace and close time per weekday ([decision D5](docs/decisions.md)). Empty = the defaults. |
| `HOLIDAYS` | no | Comma-separated dates that aren't working days, e.g. `2026-12-25,2026-12-26`. |
| `EXTRA_ORIGINS` | no | Development only: extra web addresses allowed to use Face ID (the Vite dev server). |
| `SESSION_DAYS` | no (`30`) | How long a sign-in lasts. |

Changing `SCHEDULE_JSON`, `HOLIDAYS`, `COMPANY_NAME` or `PRIVACY_CONTACT` needs a restart, not a rebuild.

## Deploying and backups

[`docs/deploy-railway.md`](docs/deploy-railway.md) covers creating the Railway project, the
variables, the HTTPS address, creating the MD and the manager, turning on backups, and a safe way to
check that a backup can be restored.
