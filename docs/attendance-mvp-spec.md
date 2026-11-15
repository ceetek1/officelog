# Workplace Attendance — MVP Spec

> **For the AI coding agent (Claude Code / Cursor).** Build exactly this, nothing more. The full product is described in `attendance-spec.md`; treat it as the roadmap for *after* the MVP, and do not build its extra features now. If this file and the full spec disagree, **this file wins** for the MVP. If anything is unclear, **stop and ask the human**. "MUST" and "MUST NOT" are hard rules.
>
> **How to work:** first ask the human the questions in §14. Then build **one step of §11 at a time**. At the end of each step, stop and show the human: what you built, the tests you ran and their results, and anything they must check by hand. **Wait for the human's OK before starting the next step.**

---

## 1. What the MVP must prove

**Will every worker clock in and out every working day, with little friction?** Every feature below either serves that, or is the minimum needed to run a fair test at a real company (under 20 workers, one entrance, Starlink internet). The MVP also **measures** that daily use (§9), because a test with no numbers proves nothing.

## 2. Roles

| | Worker | Manager | MD |
|---|---|---|---|
| Clocks in and out | yes | **yes** (the manager is also a worker) | no |
| Sees own times and history | yes | yes | — |
| Sees everyone's times | no | yes | yes |
| Submits reasons for own late / absent / missed clock-out | yes | yes | no |
| Approves or rejects **workers'** reasons | no | yes | yes |
| Approves or rejects the **manager's** reasons | no | **no** (nobody approves their own) | yes |
| Overrides any decision | no | no | yes |
| Adds, deactivates workers; resets a lost phone | no | yes | no |
| Sets up or revokes the entrance kiosk | no | yes | no |
| Sees the activity log and the usage numbers | no | no | yes |
| Edits a recorded time directly | **no** | **no** | **no** |

- Every permission MUST be checked in the backend on every request. The UI hiding a button is never the check.
- A user MUST NOT decide on their own reason. The backend MUST enforce this, even though the rules above already route the manager's reasons to the MD.
- The manager uses the **phone app** for everything: clocking in and out, plus the manager screens. The MD uses **email + password** on any device.
- The developer creates the MD and the manager with the admin CLI (§8). The manager then adds workers.

## 3. Rules

Company timezone: `Africa/Lagos`. In the MVP, the settings are **environment variables**, set by the developer: `START_TIME=08:00`, `GRACE_MINUTES=10`, `CLOSE_TIME=17:00`, `MISSING_OUT_TIME=18:00`, `WEEKLY_OFF=6,7` (Saturday and Sunday), `HOLIDAYS=` (comma-separated dates).

| Term | Rule |
|---|---|
| work_date | The calendar date in Africa/Lagos of the **server** time at the scan |
| Late | Clock-in after start + grace. Late minutes are counted from the **start time**. Example: start 08:00, grace 10: 08:10:00 is on time; 08:10:01 is late by 10 minutes; 08:11 is late by 11. |
| Absent | A working day with no clock-in by close time |
| Missing clock-out | Clocked in, with no clock-out scan and no approved claimed time by the missing-out time |
| Hours worked | Clock-out minus clock-in, when both exist |
| Excused | A late arrival or absence with an approved reason. The late flag and minutes stay, marked as excused. |

- One clock-in and one clock-out per person per work_date. A second clock-in returns `409` with the existing time. A clock-out with no clock-in that day returns `409`.
- Clocking out less than 5 minutes after clocking in needs `confirm: true` from the client.
- Weekends and holidays are never counted as late or absent, but scans on those days are still recorded.
- Times come from the server clock only. Business logic MUST get "now" from an injectable `Clock`, never from `datetime.now()` directly, so tests can simulate any time.
- Deactivated users are excluded from absence counts.

## 4. Flows

### 4.1 Onboarding (the manager adds a worker)
1. The manager adds a name and gets an **invite link + QR code**. The invite is a 32-byte random token; only its SHA-256 hash is stored. Single-use, expires in 48 hours.
2. The worker opens it on their own phone, reads the privacy notice (§7), and sets a **6-digit PIN**.
3. The server creates a **device token** (32 random bytes). The phone stores it in `localStorage`; the server stores only its hash. The worker now has **one active device**.
4. Login on that phone = PIN + device token. A login with a valid PIN but an unknown device token is rejected with the message: "This phone isn't registered. Ask your manager to reset your phone."

> **iPhone gotcha:** an app added to the home screen keeps its storage separate from Safari. The registration screen MUST tell the worker to add the app to the home screen **first**, and to always open it from that icon.

> **Deliberately weak (MVP only):** the device token can be copied out of the phone's browser by a determined person. The signed device keys from the full spec fix this after the MVP. **Do not build them now.**

### 4.2 Clock in / clock out
1. The worker opens the app and enters their PIN. The session lasts 30 days, so in practice the PIN is rarely needed.
2. The main screen shows **one large button**: Clock in, Clock out, or "Done for today" with both times.
3. The button opens the in-app camera scanner. The worker scans the kiosk QR code. As a backup, they can type the 6-digit code shown under it.
4. The server checks: the code is valid and at most 10 seconds old, the session and device are active, and the rules in §3 allow the scan.
5. **Receipt:** "Clocked in 08:04 · on time" or "Clocked in 08:23 · 23 min late · Add a reason". Clock-out receipts show the hours worked.
6. The kiosk's **"Just arrived"** list shows the person's first name and the time for 60 seconds (the last 5 scans).

### 4.3 Reasons and decisions
- Reason types: `late`, `absent`, `missed_clock_out`. One per type per work_date, submitted up to 7 days later, and editable only while pending.
- `missed_clock_out` needs a `claimed_time` after the clock-in, on the same work_date. When it's approved, it becomes the clock-out, shown as "claimed 17:40 · approved by <name>".
- The manager decides on workers' reasons. The MD decides on the manager's reasons. The MD can **override** any decision at any time.
- Decisions are **append-only**: an override adds a new row, and the newest row is the one that counts. Every decision has an optional note.

### 4.4 Phone reset and kiosk
- **Reset:** the manager revokes the worker's device, and a new invite is created. Every reset shows in the MD's activity log, because a reset could be used to hand someone's account to another person.
- **Deactivate:** the user can no longer log in or scan, and their history is kept.
- **Kiosk:** the manager creates a setup link and opens it on the entrance device, which then stores a kiosk token. The manager can revoke it.

## 5. Rotating code

- `window = floor(unix_seconds / 5)`. `day_secret = HMAC-SHA256(MASTER_SECRET, "kiosk:" + work_date)`. `MASTER_SECRET` comes from an environment variable.
- `code` = 6 digits, using RFC 4226 dynamic truncation of `HMAC-SHA256(day_secret, window as 8-byte big-endian)`.
- QR content: `ATT1.<window>.<code>`. Accept only if `window` is the current one or the one before it.
- The kiosk polls `GET /api/kiosk/code` every second and holds no secret. If polling fails for 10 seconds, it shows "Connection lost — scans paused".
- **Accepted risk, decided by the human:** there is no GPS, IP or Wi-Fi check, because Starlink makes an IP check unreliable. A live relay over video is possible. **Do not add location checks.**

## 6. Data

| Table | Columns | Constraints |
|---|---|---|
| `users` | id, name, email (MD only), role (`worker`/`manager`/`md`), pin_hash, password_hash, active, created_at | exactly one active `md` and one active `manager` |
| `devices` | id, user_id, token_hash, registered_at, revoked_at | one active device per user (partial unique index) |
| `invites` | id, user_id, token_hash, created_by, expires_at, used_at | token_hash unique |
| `kiosks` | id, token_hash, created_by, created_at, revoked_at | |
| `sessions` | id, user_id, csrf_token, expires_at, revoked_at | |
| `scans` | id, user_id, kind (`in`/`out`), server_time, work_date, kiosk_window, ip | unique (user_id, work_date, kind) |
| `scan_attempts` | id, user_id nullable, result (`ok` or error code), client_ms_to_scan, created_at | every attempt, including failures (§9) |
| `reasons` | id, user_id, work_date, type, claimed_time, text (max 500), created_at, updated_at | unique (user_id, work_date, type) |
| `decisions` | id, reason_id, actor_id, decision, note, is_override, created_at | append-only |
| `activity_log` | id, actor_id, action, entity, entity_id, before jsonb, after jsonb, created_at | app database role: INSERT and SELECT only |

The day view (times, late, absent, excused, missing clock-out, hours) is **calculated** from these tables by pure functions in `app/rules/`, which have no database or framework imports. It is never stored or edited.

Write to `activity_log` for: user add/deactivate, device reset, invite create, kiosk create/revoke, reason create/edit, decisions, overrides, and failed logins.

## 7. Privacy (Nigeria Data Protection Act 2023)

The onboarding screen shows a short notice: what is collected (name, clock times, a device token, and the IP address of each scan), why it's collected, who sees it (the manager and the MD), how long it's kept (for the length of the test, then deleted unless the company adopts the system), and who to contact. Collect nothing else: no GPS, no photos.

## 8. Stack and admin

- **Backend:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, psycopg 3, argon2-cffi, pytest.
- **Database:** Postgres 16.
- **Frontend:** TypeScript, React, Vite, a QR scanner library tested on iOS Safari, and a QR generator. Pin exact versions.
- **Deploy:** one Docker image. FastAPI serves the frontend at `/` and the API at `/api` on one origin, over HTTPS (phone cameras need it). Managed Postgres.
- **Security basics:** argon2id for PINs and passwords; httpOnly, Secure, SameSite=Lax cookies plus a CSRF header; 5 failed logins per device or email in 15 minutes locks that device or email for 15 minutes.
- **Admin CLI:** `python -m app.admin create-md --name --email` and `python -m app.admin create-manager --name` (prints the manager's invite link).

## 9. Usage measurement (the point of the MVP)

The MD's **Usage** page and `python -m app.admin usage --from --to` show, per day and in total:
- the % of active people with both a clock-in and a clock-out on each working day
- the first-try scan success rate (from `scan_attempts`)
- the median time from tapping the button to the receipt (`client_ms_to_scan`, measured by the app)
- failed attempts grouped by error code (stale code, already clocked in, not logged in, and so on)
- missing clock-outs per day, and reasons submitted per day

## 10. Screens

The product should feel calm, fast and certain: every action ends with a receipt. Large touch targets (44 px or more). It must work on a 360 px-wide phone. Status words are always written out, never shown as colour alone.

- **Worker / manager phone app:** Today (the big button + today's times + "Add a reason" when relevant), History by month, My reasons. Managers also get: **Team today**, **Approvals**, **People** (add, deactivate, reset phone), **Kiosk**.
- **Kiosk:** a full-screen QR code, the 6-digit code in large digits, a 5-second countdown bar, and the "Just arrived" list. Readable from 1 metre away.
- **MD (web):** Today board, history per person, Approvals (the manager's reasons) with Override on every decision, Activity log, and Usage.

## 11. Build steps

Build in this order. After each step, **stop, report, and wait for the human's OK.** "Human checks" are things only a person with real phones can do: list them clearly in your report, and do not claim them as done.

| Step | Build | Agent's done check | Human checks |
|---|---|---|---|
| 1 | Repository, Docker image, migrations, admin CLI, MD password login, sessions and CSRF, a local run with Postgres, deploy instructions for HTTPS | Tests pass; a worker endpoint called as the MD returns 403 | The site runs over HTTPS and the MD can log in |
| 2 | Kiosk code + screen, invites, PIN + device token, clock in and out, receipts, "Just arrived", `scan_attempts` | Tests: a 15-second-old code, a second clock-in and an unregistered device token are all rejected | A real Android phone and a real iPhone (home-screen app) both clock in and out from the kiosk |
| 3 | `app/rules/` with tests, Today and History screens, manager's Team today | Every rule test in §12 passes | The times shown match the scans just made |
| 4 | Reasons, manager approvals, MD approvals of the manager's reasons, MD override, activity log | The manager deciding on their own reason returns 403; an override changes the result and appears in the activity log | Submit and approve a reason from a phone |
| 5 | People (add, deactivate, reset phone), kiosk setup and revoke | A reset device can't log in; the new invite works; the reset appears in the activity log | Reset a real phone and register it again |
| 6 | MD Today board, Usage page and CLI, privacy notice, README (setup, env vars, deploy, admin commands) | Usage numbers match a scripted set of test scans; 20 scans within one minute all succeed | Read the privacy notice; restore a database backup once |

## 12. Required tests

- Late boundaries: 08:10:00 on time, 08:10:01 late by 10 minutes, 08:11 late by 11 minutes.
- Absent on a working day; not absent on a weekend, a holiday, or for a deactivated user.
- Hours with a scanned clock-out and with an approved claimed clock-out.
- The latest decision wins; an MD override flips the result.
- A code from the previous window is accepted; one two windows old is rejected.
- A second clock-in is rejected; a clock-out with no clock-in is rejected.
- Every endpoint, called with the wrong role, returns 403. One test MUST walk through the whole table in §2, including "the manager decides on own reason → 403".
- The app's database role cannot UPDATE or DELETE `activity_log`.

## 13. NOT in the MVP (build later, from the full spec)

Signed device keys (WebCrypto) · daily summary email · monthly CSV report · MD settings screen (environment variables for now) · holidays screen (environment variable for now) · retention job · multiple managers · breaks and shifts · location checks of any kind · native apps · offline mode.

## 14. Questions to ask the human before Step 1

1. Confirm the times with the company: start 08:00, grace 10 minutes, close 17:00, Saturday and Sunday off.
2. What device will run the kiosk, and can it stay plugged in near the door?
3. Is there exactly **one** manager? The MVP assumes so.
