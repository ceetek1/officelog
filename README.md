# OfficeLog

OfficeLog is a daily attendance log for workers. It records when each worker clocks in and when
they clock out.

## How it works

1. **The entrance TV shows a code.** A QR code that changes every 5 seconds, with a 6-digit code
   under it that changes every 30 seconds.
2. **The worker scans it with their phone** and confirms with Face ID. The server checks that the
   code is current and that it's really that person on their registered phone, then saves the time.
3. **The phone shows a receipt:** the time, and whether they were on time or how many minutes late.
   Leaving works the same way, and leaving before closing time is marked "Left early".
4. **The day is worked out from the times,** using each weekday's start, grace period and close
   time: on time, late, left early, absent, or no clock-out.
5. **Workers can explain.** A late, absent or early day can get a reason. The manager approves or
   rejects workers' reasons; the managing director (MD) decides the manager's and can override any
   decision.
6. **Nothing recorded is ever changed.** If a phone or the TV fails, the manager adds the time from
   the paper sheet as a new entry marked "added from paper". Every important action goes into an
   activity log that the MD can read.
7. **The MD sees everything:** any day, each person's history, and usage numbers showing whether
   people actually clock in and out with the app.

The backend is Python (FastAPI) with Postgres; the app for phones, the MD and the TV is React and
TypeScript. Face ID uses WebAuthn passkeys.

## Run it locally

You need Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 22+, and Postgres 16.

```bash
cp .env.example .env
```

Set `DATABASE_URL`, `APP_DB_PASSWORD` and `MASTER_SECRET` in `.env`, then:

```bash
uv sync && (cd frontend && npm ci && npm run build)
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

Open <http://localhost:8000/md/login>. Phones need HTTPS for the camera and Face ID, so test on
real phones against a deployed copy.

## Documentation

- [What OfficeLog does](docs/overview.md): roles, a working day, privacy, and why it's built this way
- [How the code is put together](docs/architecture.md): modules, how they connect, and the frontend
- [Data and rules](docs/data-and-rules.md): tables, attendance rules, pages and permissions
- [Running and deploying](docs/operations.md): tests, admin commands, settings, Railway, backups
