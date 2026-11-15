# Decisions that change the spec

The spec is [`attendance-mvp-spec.md`](attendance-mvp-spec.md). The decisions below were made by the
product owner on **2026-11-15**, after the spec was written and after the UI ("Prototype B") was
designed. **Where a decision and the spec disagree, the decision wins.** Each entry says what the spec
said, what we do instead, and why.

The UI is Prototype B, from the Claude Design artifact
<https://claude.ai/artifact/J938HvLRWKM5zqFLMvuUrR> (files `project/B_*.dc.html`). It is rebuilt as
React components, not pasted.

---

## D1. Sign-in is Face ID (passkeys), not a PIN

- **Spec said:** 6-digit PIN + a device token in `localStorage` (§4.1, §4.2, §6 `pin_hash`, `devices.token_hash`).
- **We do:** WebAuthn passkeys on the phone's built-in authenticator, with user verification required
  (`authenticatorAttachment: platform`, `userVerification: required`). On phones without Face ID it
  falls back to fingerprint or the phone passcode, which the phone handles by itself.
  - The invite link registers the passkey on the worker's phone. That passkey is their **one active
    device** (the `devices` table holds the credential; one active row per user).
  - **Login and every clock in / clock out need a passkey assertion.** The phone shows the Face ID
    prompt between the scan and the receipt.
  - **Reset phone** revokes the credential and creates a new invite. It is written to the activity log.
  - Kept from the spec: the 30-day session; the message "This phone isn't registered. Ask your
    manager to reset your phone."; the instruction to add the app to the home screen **first**; the
    failed-login lockout (5 failures in 15 minutes locks for 15 minutes).
  - Library versions are pinned: `webauthn` (Python) and `@simplewebauthn/browser`.
  - The MD still signs in with **email + password**.
- **Why:** the owner wants Face ID. A passkey can't be copied out of the phone the way a
  `localStorage` token can, so this also removes the "deliberately weak" device token from §4.1.
- **Effect on data:** `users.pin_hash` is dropped. `devices` stores the WebAuthn credential id, public
  key and sign count instead of a token hash.

## D2. Rotating codes: made by the server now, ready for the TV to make them later

- **Spec said:** §5. The server makes the code; the kiosk polls `GET /api/kiosk/code`; a scanned code
  is accepted for the current and previous 5-second window.
- **We do:**
  - As the spec: the **server** makes the codes. The TV polls `GET /api/kiosk/code`. The **QR changes
    every 5 s** and is accepted for the current window and the one before.
  - **The typed 6-digit code changes every 30 s** and is accepted for the 30 s it is shown, plus a
    few seconds of slack, because nobody can type 6 digits in 10 s.
  - **Designed for a future offline mode**, not built now: the code algorithm lives in one pure,
    documented module that can run on the server and in the TV's browser, and the per-kiosk secret is
    obtained through an interface. A later version can let the TV keep its own secret and make codes
    without internet, **without changing the QR format or the scan API**.
  - Tests cover a stale QR code and a stale typed code.
- **Why:** the typed code must be typeable; the office internet may be unreliable later.
- **Note:** the design canvas says "Codes are made on the TV". That describes the future mode; for
  now the server makes them.

## D3. Time from the paper sheet

- **Spec said:** nobody edits a recorded time (§2).
- **We do:** the manager can add a clock-in and/or clock-out for a person from the paper sheet, and
  must choose why: **"TV not working"**, **"No smartphone"**, or **"Phone dead or forgotten"**.
  - It is stored as a scan with `source = 'paper'` and `entered_by`. It can never be edited, it always
    appears in the activity log, and it is shown as "added from paper by <name>".
  - **Answered 2026-11-15:** the manager **may** enter their own paper time. It is still logged and
    shown as "added from paper by <name>", so the MD can see it.
- **Why:** some workers have no smartphone, and the TV or a phone can fail. This deliberately relaxes
  "nobody edits a recorded time": it adds a time, visibly and permanently, instead of changing one.

## D4. Left early

- **Spec said:** reason types `late`, `absent`, `missed_clock_out`.
- **We do:** add reason type **`left_early`**. A clock-out before that day's close time is flagged
  **"Left early · N min"** in the day view (pure rules in `app/rules/`, with tests). The worker can
  send a reason for it.

## D5. Schedule per weekday, changeable without a rebuild

- **Spec said:** one `START_TIME`, `GRACE_MINUTES`, `CLOSE_TIME`, `MISSING_OUT_TIME`, `WEEKLY_OFF`.
- **We do:** one environment variable, `SCHEDULE_JSON`, holding the schedule per weekday. Changing it
  needs a restart, not a rebuild. Defaults:

  | Day | Start | Grace | Close | Notes |
  |---|---|---|---|---|
  | Mon, Tue, Wed, Fri | 08:00 | 10 min | 17:00 | |
  | Thu | 10:00 | 5 min | 15:00 | confirmed 2026-11-15 |
  | Sat | 08:00 | 5 min | 15:00 | start may change |
  | Sun | off | | | |

  - The **missing clock-out** cutoff is per day: **close + 60 minutes** (`missing_out_after`),
    confirmed 2026-11-15. So Mon–Wed and Fri 18:00, Thu and Sat 16:00.
  - Holidays stay an environment variable (`HOLIDAYS`, comma-separated dates).
  - The §12 late-boundary tests are extended for Thursday and Saturday.

## D6. One manager; hosted on Railway

- **Spec said:** exactly one manager (§2); "one Docker image … managed Postgres" (§8).
- **We do:** exactly one active manager, as the spec. Hosting is **Railway**: the Docker image plus
  Railway's managed Postgres, served over HTTPS. Deploy instructions are in
  [`deploy-railway.md`](deploy-railway.md). The owner creates the Railway account; the builder never
  signs up for anything on the owner's behalf.

## D7. Pace

Step by step, as the spec says: after each step of §11 the builder stops, reports what was built,
the tests and their results, and what must be checked by hand on real phones, then waits for the
owner's OK.

## D8. UI = Prototype B

iPhone-native patterns (large titles, back buttons, bottom tab bars, sheets with Cancel / Send, inset
grouped lists, system-style alerts). Font: Atkinson Hyperlegible Next, and Atkinson Hyperlegible Mono
for times and codes. Background `#FAFAFA`; cards white, 1px `#E5E5E5` border, 12px corners; text
`#171717`; main buttons `#1D4ED8` (hover `#1E40AF`). Status always shown as a word plus a tint. Works
at 360 px wide. The TV board (1920×1080, light) must run in a smart TV's built-in browser: build
target about ES2019, no interaction needed, reloads itself if stuck, and shows "Connection lost".

---

## Builder's choices (made while building; the owner may change them)

These are small choices the spec leaves open. They are listed so a reviewer sees them.

- **B1. Database role for the app.** The app connects as a separate role (`attendance_app`) that may
  only `SELECT` and `INSERT` on `activity_log`, `scans` and `decisions`. This is how "append-only" and
  "nobody edits a recorded time" are enforced by the database, not only by the code. Migrations run
  as the database owner. `activity_log` also has a trigger that refuses `UPDATE` and `DELETE` for
  everyone.
- **B2. Session length.** All sessions last 30 days, the MD's included.
- **B3. Session cookie.** The cookie holds a random token; the database stores only its SHA-256 hash.
- **B4. Fonts are bundled** with the app (from `@fontsource`), not loaded from Google, so the TV and
  phones need no third-party request and nothing is shared with Google.
- **B5. The clock time is when the code was checked.** Clocking is two calls: the phone sends the
  scanned code (the server checks it and notes the time), then Face ID's answer (the server records
  the scan with the noted time). So a slow Face ID prompt can't make someone late or let a stale
  code through.
- **B6. Admin commands for people and the TV.** Before Step 5's screens existed, workers were added
  and the TV paired with `create-worker` and `create-tv-link`. Both still work and do exactly what the
  manager's screens do (same activity log entries). TV setup codes work once, for 24 hours.
- **B7. Old TV browsers.** The build adds a second, "legacy" bundle with polyfills for browsers too
  old for modern JavaScript, so older Samsung and LG TVs can run the board. The TV layout uses only
  flexbox without `gap`, which old browsers lack.
- **B8. When the TV loses the server,** it hides the QR and typed code after 10 seconds (they'd be
  stale) and shows "Connection lost · scans paused". It recovers by itself, reloads itself if its
  loop stops, when a new version is deployed, and once a day around 04:00.
- **B9. Day status words.** A day shows one main word in lists, in this order of importance:
  Absent (or Excused), No clock-out, Late (or Excused), Left early (or Excused), On time, Not in
  yet, Day off. "No clock-out" appears from close + 60 minutes. A day before today is judged as
  finished. Left early is rounded up to whole minutes (16:59:30 is 1 min early).
- **B10. The manager's own history** is a "My History" row on their Me tab, because their tab bar
  (Me, Team, Approvals, People) has no History tab in the design.
- **B11. A reason must match the day.** A late reason needs a late clock-in, left early needs an
  early clock-out, missed clock-out needs a clock-in with no clock-out, and absent needs a working
  day with no clock-in (it may be sent ahead, on the morning itself). This stops reasons for things
  that didn't happen.
- **B12. Who decides.** The manager decides workers' reasons once; a second decision by the manager
  is refused. The MD decides the manager's reasons and may also decide workers' waiting ones. Only
  the MD can change a decision, through **Override**, which adds a new decision (the old one stays,
  and the newest counts). Every decision and override is in the activity log with before and after.
- **B13. The TV is set up with a short typed code.** The design's TV screen says "Scan TV Code",
  but a TV has no camera, and typing a long link with a TV remote is painful. So the manager taps
  **Get a Setup Code** (People → Entrance TV) and gets a 10-character code like `HGDNM-46K4P`
  (about 50 bits, no look-alike letters, single use, 24 hours, only its hash is stored). On the TV's
  browser they open `/tv` and type it; upper or lower case and the dash don't matter. The full link
  (`/tv/pair/<code>`) and a QR code are also offered, for a tablet with a camera. A "TV shows a code,
  phone scans it" flow could replace this later without changing the data.
- **B14. Add person asks for the name only.** The design's Add person sheet also has a phone
  number, but the privacy notice (§7) promises we collect nothing beyond name, clock times, the
  passkey and scan IP addresses, so the number isn't asked for. The invite is shared with the
  phone's own share sheet, Copy Link, or by showing the QR code.
- **B15. Time from paper** can be added for today and up to **7 days back**, for clock-in, clock-out
  or both at once. Times already recorded are shown and can't be replaced; the same rules as
  scanning apply (one of each per day, a clock-out after a clock-in, nothing in the future). The
  MD's Today page has the same **Time from Paper** button as the manager's Team page.
- **B16. Nobody resets or deactivates themselves on the screens.** The manager can't reset their own
  phone (they'd need it to do so) or deactivate themselves, and the manager can't be deactivated
  from the app (there must be exactly one). If the manager loses their phone, the developer runs
  `python -m app.admin reset-phone --name "<name>"`, which is logged like a reset on the screen.
  Deactivating also revokes the person's phone, signs out every session and cancels open invites.
  There's no "reactivate" in the MVP: add the person again.
- **B17. "New Invite Link" is a phone reset.** For someone whose invite expired or who has no phone
  yet, the People screen offers "New Invite Link". It uses the same action as Reset Phone (old
  invites stop working, a new one is made) and shows in the activity log as "Phone reset", so the MD
  sees every new invite for an existing person.
- **B18. TV status.** "Online" means the TV asked for a code in the last 2 minutes, otherwise
  "Offline". "Scans today" counts every QR and typed scan today, because the codes aren't tied to
  one TV.
