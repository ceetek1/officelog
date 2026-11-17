# Running, deploying and looking after OfficeLog

## Run it on your computer

You need Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 22 or newer, and Postgres 16.

```bash
cp .env.example .env
```

Edit `.env`: point `DATABASE_URL` at your Postgres and set `APP_DB_PASSWORD` and `MASTER_SECRET`
to long random strings. Then:

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

Open <http://localhost:8000/md/login>. For frontend work with hot reload, also run `npm run dev`
in `frontend/` and open <http://localhost:5173> (add it to `EXTRA_ORIGINS` for Face ID).

Or, with Docker, start Postgres and the app together at <http://localhost:8000>:

```bash
docker compose up --build
```

Then create the MD inside the app container:

```bash
docker compose exec app python -m app.admin create-md --name "Your Name" --email you@example.com
```

Phones need **HTTPS** for the camera and Face ID, so test on real phones against the deployed site
(or another HTTPS address), not `http://localhost` from another device.

## Tests

The backend tests create and drop a database called `officelog_test` on the Postgres server you
give them:

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
| `migrate` | Updates the database and the app's restricted database role. Runs on every container start. |
| `create-md --name --email` | Creates the MD (asks for a password; `--password-stdin` to pipe it). |
| `reset-md-password --email` | Sets a new password for the MD. |
| `create-manager --name` | Creates the manager and prints their one-time invite link. The MD can do the same in the app: MD → People → **Add Manager**. |
| `create-worker --name` | Creates a worker and prints their invite link (normally the manager uses People). |
| `reset-phone --name` | Revokes a person's phone and sessions and prints a new invite link. Use it when the manager loses their own phone. |
| `create-tv-link` | Prints a one-time TV setup link and code (normally the manager uses People → Entrance TV). |
| `usage [--from YYYY-MM-DD] [--to YYYY-MM-DD]` | Prints the usage numbers per working day and in total. Default: the last 14 days. |

Everything these commands change is written to the activity log, the same as from the screens.

## Environment variables

Set them in `.env` locally, or as service variables when deployed. [`.env.example`](../.env.example)
has the same list with comments.

| Variable | Needed | What it is |
|---|---|---|
| `DATABASE_URL` | yes | The database owner's address. Used to run migrations and to create the app's restricted role. `postgres://` addresses are accepted. |
| `APP_DB_ROLE` | no (`attendance_app`) | The restricted role the app runs as. |
| `APP_DB_PASSWORD` | yes | That role's password: at least 12 characters, ideally a long random string. |
| `APP_DATABASE_URL` | no | A full address for the app role, if it can't be built from `DATABASE_URL`. |
| `MASTER_SECRET` | yes | Makes the TV's rotating codes. At least 32 random characters; keep it secret. |
| `BASE_URL` | yes | The site's public address, no trailing slash. Used in invite links, and Face ID passkeys belong to its host name. |
| `COOKIE_SECURE` | yes when deployed (`true`) | `false` only for `http://localhost`. |
| `COMPANY_NAME` | no | Shown on the sign-in screen and in the privacy notice. |
| `PRIVACY_CONTACT` | recommended | Who to contact about personal data, shown in the privacy notice. |
| `TIMEZONE` | no (`Africa/Lagos`) | The company's timezone. |
| `SCHEDULE_JSON` | no | Start, grace and close per weekday (see [data-and-rules.md](data-and-rules.md#the-schedule)). Empty = the defaults. |
| `HOLIDAYS` | no | Comma-separated dates that aren't working days, e.g. `2026-12-25,2026-12-26`. |
| `SESSION_DAYS` | no (`30`) | How long a sign-in lasts. |
| `EXTRA_ORIGINS` | no | Development only: extra web addresses allowed to use Face ID (the Vite dev server). |
| `FRONTEND_DIST` | no (`frontend/dist`) | Where the built frontend is. Empty serves the API only. |
| `RAILWAY_GIT_COMMIT_SHA` | set by Railway | Identifies the running build; the TV reloads itself when it changes. |

Changing `SCHEDULE_JSON`, `HOLIDAYS`, `COMPANY_NAME` or `PRIVACY_CONTACT` needs a restart, not a
rebuild.

**Choose `BASE_URL` before anyone registers a phone.** Passkeys belong to that host name; moving to
a new address (for example a custom domain) means every phone has to register again.

## Deploying on Railway

Railway builds the `Dockerfile` (see `railway.json`), runs it next to a managed Postgres, and gives
the site an HTTPS address. The container runs `scripts/start.sh`: `migrate`, then uvicorn on
`$PORT`. Railway checks `/api/health` before switching traffic to a new version.

1. **Project and database.** In Railway: **New Project → Deploy from GitHub repo**, pick this
   repository. Then **New → Database → PostgreSQL** (version 16; 17 also works). The first deploy
   fails until the variables are set.
2. **Variables.** On the app service → **Variables**, set `DATABASE_URL` to
   `${{Postgres.DATABASE_URL}}` (Railway fills it in), plus `APP_DB_PASSWORD`, `MASTER_SECRET`,
   `BASE_URL`, `COOKIE_SECURE=true`, `COMPANY_NAME`, `PRIVACY_CONTACT`, and optionally `TIMEZONE`,
   `SCHEDULE_JSON`, `HOLIDAYS`. Make random strings with
   `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`.
3. **HTTPS address.** Service → **Settings → Networking → Generate Domain**. Put that address in
   `BASE_URL`. Add a custom domain here *before* inviting anyone, if you want one.
4. **Deploy and check.** Deploy (or push to the deployed branch). When it's green,
   `https://<address>/api/health` shows `{"ok":true}`.
5. **Create the MD.** With the [Railway CLI](https://docs.railway.com/guides/cli): `railway login`,
   `railway link`, `railway ssh`. Inside the container, use `/opt/venv/bin/python` (an SSH session
   doesn't get the image's `PATH`, so plain `python` lacks the app's libraries):

   ```bash
   /opt/venv/bin/python -m app.admin create-md --name "Folake Adeyemi" --email folake@example.com
   ```

   The MD then signs in at `https://<address>/md/login` and adds the manager from MD → People. The
   manager adds workers and sets up the TV from their phone.

## Backups

On Railway's Postgres service, open **Backups** and turn on scheduled backups. Restoring one there
replaces the live data, so only do it when something has really gone wrong.

To check that a backup can be restored without touching the live site, copy the database to your
own computer (Postgres 16 tools needed). Take `DATABASE_PUBLIC_URL` from the Postgres service's
**Variables**, then:

```bash
pg_dump --format=custom --no-owner --file=officelog-backup.dump "<DATABASE_PUBLIC_URL>"
```

```bash
createdb officelog_restore_check
```

```bash
pg_restore --no-owner --dbname=officelog_restore_check officelog-backup.dump
```

```bash
psql officelog_restore_check -c "select name, role, active from users" -c "select count(*), max(server_time) from scans"
```

The people and the latest scans should be there. Then delete both, because the file holds
everyone's attendance data:

```bash
dropdb officelog_restore_check && rm officelog-backup.dump
```
