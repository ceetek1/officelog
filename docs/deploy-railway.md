# Deploying on Railway

Railway runs the app's Docker image and a managed Postgres database, and gives the site an HTTPS
address (phone cameras and Face ID only work over HTTPS). See [decision D6](decisions.md).

**You create the Railway account yourself.** Nothing here signs up for anything on your behalf.

## What you need

- A Railway account (<https://railway.com>), linked to the GitHub account that holds this
  repository (`ceetek1/officelog`).
- The code merged into the branch Railway deploys from (normally `main`).

## 1. Create the project and the database

1. In Railway, click **New Project → Deploy from GitHub repo** and pick `officelog`.
   Railway finds the `Dockerfile` and `railway.json` and builds the image. The first deploy will
   fail until step 2 is done; that's expected.
2. In the same project, click **New → Database → PostgreSQL**. If Railway lets you choose a
   version, choose **16** (the spec's version; 17 also works).

## 2. Set the app's variables

Open the **officelog** service → **Variables**, and add:

| Variable | Value |
|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (type it exactly like this; Railway fills it in) |
| `APP_DB_PASSWORD` | a long random string, e.g. from `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `BASE_URL` | the site's address from step 3, e.g. `https://officelog-production.up.railway.app` (no trailing slash) |
| `COOKIE_SECURE` | `true` |
| `COMPANY_NAME` | your company's name, shown on the sign-in screen |
| `TIMEZONE` | `Africa/Lagos` |
| `SCHEDULE_JSON` | leave empty for the default schedule (see [decisions.md](decisions.md), D5), or paste your own |
| `HOLIDAYS` | comma-separated dates, e.g. `2026-12-25,2026-12-26,2027-01-01` |

`DATABASE_URL` is the database owner. On every start the app uses it to update the database and to
create its own restricted user (`attendance_app`, with `APP_DB_PASSWORD`). The app then runs as that
restricted user, which cannot change recorded times or the activity log.

## 3. Give the site an HTTPS address

Service → **Settings → Networking → Generate Domain**. Railway issues the HTTPS certificate itself.
Copy the address into `BASE_URL` (step 2). A custom domain can be added here later; if you do,
update `BASE_URL` too.

## 4. Deploy and check

Click **Deploy** (or push to `main`). When the deploy is green, open
`https://<your-address>/api/health`. It should show `{"ok":true}`.

## 5. Create the MD and the manager

Install the Railway command line (<https://docs.railway.com/guides/cli>), then in this repository:

```bash
railway login
```

```bash
railway link
```

```bash
railway ssh
```

You are now inside the running app. Create the MD (you'll be asked for a password twice; at least 10
characters):

```bash
python -m app.admin create-md --name "Folake Adeyemi" --email folake@example.com
```

Create the manager. This prints an invite link that works once, for 48 hours, on the manager's own
phone:

```bash
python -m app.admin create-manager --name "Emeka Okonkwo"
```

Type `exit` to leave. Other commands: `python -m app.admin --help`.

The MD signs in at `https://<your-address>/md/login`.

## Backups

Railway's Postgres service has a **Backups** tab. Turn on scheduled backups there. Step 6 of the
build asks you to restore one backup once, to be sure it works.

## Changing settings later

Change a variable in Railway and the app restarts with it. No rebuild is needed for `SCHEDULE_JSON`,
`HOLIDAYS`, `COMPANY_NAME` or `BASE_URL`.
