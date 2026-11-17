# Data and rules

## Tables

Defined in `app/models.py`, created by the migrations in `migrations/versions/`. Times are stored
in UTC (`timestamptz`); `work_date` is the calendar date in the company's timezone. Nothing derived
(late, absent, hours) is stored: it is worked out from the facts each time by `app/rules/day.py`.

| Table | Holds | App may |
|---|---|---|
| `users` | Everyone: name, role (`worker`, `manager`, `md`), active. Email and password hash for the MD only. At most one active MD and one active manager (unique index). | read, add, update |
| `devices` | A person's registered phone: the passkey's credential id, public key and sign count. One active device per person. | read, add, update |
| `invites` | One-time invite links (only the token's hash), with expiry and when used. | read, add, update |
| `sessions` | Sign-ins: token hash, CSRF token, the phone used, expiry, revoked. | read, add, update |
| `webauthn_challenges` | One-time Face ID challenges for register, login and clock. A clock challenge carries what `/clock/start` checked (kind, time, code window). | read, add, update, delete |
| `kiosks` | The entrance TV: setup code hash and expiry, the TV's token hash once paired, last seen, revoked. | read, add, update |
| `scans` | Each clock-in and clock-out: who, `in` or `out`, server time, work date, source (`qr`, `typed`, `paper`), IP. Paper rows also record who entered them and why. One of each kind per person per day. | **read, add only** |
| `scan_attempts` | Every attempt to clock, successful or not, with the result code, method and the phone's tap-to-receipt time. | **read, add only** |
| `reasons` | A reason for a day: type (`late`, `absent`, `left_early`, `missed_clock_out`), text, and the claimed time for a missed clock-out. One per type per person per day. | read, add, update |
| `decisions` | Approve or reject a reason, by whom, with a note, and whether it was an MD override. The newest row for a reason counts. | **read, add only** |
| `activity_log` | Who did what, to what, with before and after values. | **read, add only** (plus a trigger that blocks changes for everyone) |
| `login_failures` | Failed sign-ins, for the lockout. | read, add, update, delete |

### Who can change what in the database

The app does not connect as the database owner. On every start, `python -m app.admin migrate`
runs the migrations as the owner (`DATABASE_URL`) and then `app/dbrole.py` creates or updates a
restricted role (`APP_DB_ROLE`, default `attendance_app`) with the privileges in the table above.
The web app connects as that role. So "a recorded time is never edited" and "the activity log is
append-only" hold even if the application code had a bug.

## The schedule

Set per weekday with `SCHEDULE_JSON`; holidays with `HOLIDAYS`. The defaults
(`app/rules/schedule.py`):

| Day | Start | Grace | Close | "No clock-out" from |
|---|---|---|---|---|
| Mon, Tue, Wed, Fri | 08:00 | 10 min | 17:00 | 18:00 |
| Thu | 10:00 | 5 min | 15:00 | 16:00 |
| Sat | 08:00 | 5 min | 15:00 | 16:00 |
| Sun | day off | | | |

`SCHEDULE_JSON` format (all seven days; `null` is a day off; `missing_out_after` is optional,
default 60 minutes after close):

```json
{"mon":{"start":"08:00","grace":10,"close":"17:00"}, "…": "…", "sun":null}
```

## Rules for a day

All in `app/rules/day.py`, as pure functions of the scans, reasons, schedule and the current time.

- **Late:** clocking in after start + grace. Minutes are counted from the start time: with start
  08:00 and grace 10, 08:10:00 is on time and 08:10:01 is 10 minutes late.
- **Left early:** clocking out before close, rounded up to whole minutes (16:59:30 is 1 min early).
- **Absent:** a working day, an active person, no clock-in, and the close time has passed. Before
  that the person is "Not in yet".
- **No clock-out:** a clock-in with no clock-out once `missing_out_after` minutes past close have
  passed.
- **Hours worked:** clock-out minus clock-in.
- **Excused:** a late, absent or left-early day whose reason was approved.
- **Missed clock-out, approved:** the claimed time is used as the clock-out, shown as
  "Claimed 17:40 · approved by <name>".
- **Days off and holidays** are never late or absent, but scans on them still show.
- **Deactivated people** are never counted absent.

## Rules for clocking

In `app/api/clock.py`:

- One clock-in and one clock-out per person per day (also a unique constraint).
- A clock-out needs a clock-in first.
- Clocking out less than 5 minutes after clocking in needs a confirmation.
- The QR code is accepted for its 5-second window and the one before; the typed code for its
  30-second window, and the previous one for the first 5 seconds of a new window.
- The Face ID answer must arrive within 2 minutes of `/clock/start`; the scan is saved with the
  time noted at `/clock/start`.

## Rules for reasons

In `app/rules/reasons.py` and `app/api/reasons.py`:

- Sent by the person whose day it is, up to 7 days later, never for a future day.
- It must match what happened: *late* needs a late clock-in, *left early* an early clock-out,
  *missed clock-out* a clock-in with no clock-out, *absent* a working day with no clock-in (it may
  be sent on the morning itself).
- Editable only while waiting for a decision.
- **Who decides:** workers' reasons by the manager or the MD; the manager's reasons by the MD only.
  Nobody decides their own. A reason is decided once; after that only an override changes it.
- **Override:** only the MD, on any decided reason. It adds a new decision; the old one stays.

## Paper times

In `app/api/paper.py`. The manager or the MD adds a clock-in, a clock-out or both for one person,
for today or up to 7 days back, choosing why: *TV not working*, *No smartphone*, or *Phone dead or
forgotten*. The clocking rules above still apply, existing times can't be replaced, and the manager
may add their own. Each is a new `scans` row with `source = 'paper'` and is written to the activity
log.

## Pages and who can open them

| Address | Who | What |
|---|---|---|
| `/` | worker, manager | Today: the Clock In / Clock Out button and the day's status |
| `/history`, `/reasons` | worker, manager | History by month; my reasons |
| `/team`, `/approvals`, `/people`, `/people/tv` | manager | Team today (+ time from paper), approvals, people, entrance TV |
| `/invite/<token>` | the invited person's phone | Welcome, add to home screen, set up Face ID |
| `/tv`, `/tv/pair/<code>` | the entrance TV | The rotating code board; asks for the setup code when not paired |
| `/md/login` | MD | Email and password sign-in |
| `/md`, `/md/people`, `/md/people/<id>`, `/md/approvals`, `/md/activity`, `/md/usage` | MD | Today board (any day), people and their history, approvals and override, activity log, usage |
| `/privacy` | anyone | The privacy notice |

## What each role may do

| Action | Worker | Manager | MD |
|---|:-:|:-:|:-:|
| Clock in and out, see own history | ✓ | ✓ | |
| Send reasons for own days | ✓ | ✓ | |
| See the team's day | | ✓ | ✓ |
| Decide workers' reasons | | ✓ | ✓ |
| Decide the manager's reasons, override any decision | | | ✓ |
| Add time from paper | | ✓ | ✓ |
| Add, deactivate workers; reset a phone | | ✓ | |
| Set up or remove the entrance TV | | ✓ | |
| Add the manager, new invite for the manager | | | ✓ |
| See history per person, activity log, usage | | | ✓ |

Nobody resets or deactivates themselves from the screens, and the manager can't be deactivated from
the app. If the manager loses their phone, an operator runs `reset-phone` (see
[operations.md](operations.md)) or the MD uses **New Invite Link**.
