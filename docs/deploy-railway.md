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
| `MASTER_SECRET` | another long random string (makes the TV codes). Keep it secret. |
| `BASE_URL` | the site's address from step 3, e.g. `https://officelog-production.up.railway.app` (no trailing slash) |
| `COOKIE_SECURE` | `true` |
| `COMPANY_NAME` | your company's name, shown on the sign-in screen |
| `PRIVACY_CONTACT` | who workers contact about their data, shown in the privacy notice, e.g. `Folake Adeyemi (MD), folake@example.com, 0803 000 0000` |
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

Until the manager's People screen arrives (Step 5), add workers the same way. Each gets a one-time
link to open on their own phone:

```bash
python -m app.admin create-worker --name "Adaeze Obi"
```

And until the manager's TV screen arrives (Step 5), pair the entrance TV with a link that works once,
for 24 hours. Open it in the TV's web browser:

```bash
python -m app.admin create-tv-link
```

Type `exit` to leave. Other commands: `python -m app.admin --help`.

The MD signs in at `https://<your-address>/md/login`.

## Backups

Railway's Postgres service has a **Backups** tab. Turn on scheduled backups there. Railway can
restore one of those backups over the live database; that replaces today's data, so only do it when
something has really gone wrong.

**Check once that a backup can be restored** (spec §11, step 6), without touching the live site.
On your own computer, with Postgres 16 tools installed:

1. In Railway, open the Postgres service → **Variables** and copy `DATABASE_PUBLIC_URL`.
2. Make a copy of the live database into a file:

   ```bash
   pg_dump --format=custom --no-owner --file=officelog-backup.dump "<DATABASE_PUBLIC_URL>"
   ```

3. Restore it into a new, empty local database:

   ```bash
   createdb officelog_restore_check
   ```

   ```bash
   pg_restore --no-owner --dbname=officelog_restore_check officelog-backup.dump
   ```

4. Look at it: the people and the last scans should be there.

   ```bash
   psql officelog_restore_check -c "select name, role, active from users" -c "select count(*), max(server_time) from scans"
   ```

5. Delete the file and the local database when you're done (`dropdb officelog_restore_check`): the
   file holds everyone's attendance data.

## Important: choose the address before people register

Face ID passkeys belong to the site's host name (`BASE_URL`). If you later move to a different
address (for example a custom domain), every phone has to register again with a new invite. So set
up the custom domain, if you want one, **before** inviting workers.

## Changing settings later

Change a variable in Railway and the app restarts with it. No rebuild is needed for `SCHEDULE_JSON`,
`HOLIDAYS`, `COMPANY_NAME` or `BASE_URL`.
