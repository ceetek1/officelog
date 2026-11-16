// The workday as a thin bar: start to close, filled from clock-in to clock-out (or now).
// The gap before the fill shows lateness without a word; the words are in the status line above.

export function toMinutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

/** "HH:MM" of an instant in the company's time zone (the same zone the server uses for labels). */
export function clockTime(at: Date): string {
  return at.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Africa/Lagos" });
}

export function DayLine({ start, close, clockIn, clockOut, now }: {
  start: string; close: string; clockIn: string | null; clockOut: string | null; now: string;
}) {
  const s = toMinutes(start);
  const span = Math.max(1, toMinutes(close) - s);
  const pct = (t: string) => Math.min(100, Math.max(0, ((toMinutes(t) - s) / span) * 100));
  const fillFrom = clockIn ? pct(clockIn) : null;
  const fillTo = clockOut ? pct(clockOut) : pct(now);
  const label = `Workday ${start} to ${close}.`
    + (clockIn ? ` Clocked in at ${clockIn}.` : "")
    + (clockOut ? ` Clocked out at ${clockOut}.` : ` It is ${now}.`);
  return (
    <div className="dayline" role="img" aria-label={label}>
      <div className="dayline-track">
        {fillFrom !== null && fillTo > fillFrom && (
          <span className="dayline-fill" style={{ left: `${fillFrom}%`, width: `${fillTo - fillFrom}%` }} />
        )}
        {!clockOut && <span className="dayline-now" style={{ left: `${pct(now)}%` }} />}
      </div>
      <div className="dayline-labels" aria-hidden="true"><span>{start}</span><span>{close}</span></div>
    </div>
  );
}
