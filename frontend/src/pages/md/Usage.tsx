// MD · Usage (Prototype B "MD · Usage"; spec §9): is everyone clocking in and out, every day?
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getUsage, type Usage as Data } from "../../api";
import { PHONE, useMedia } from "../../ui/useMedia";
import { MdShell } from "./Shell";

const pct = (v: number | null) => (v === null ? "--" : `${v}%`);
const secs = (ms: number | null) => (ms === null ? "--" : `${(ms / 1000).toFixed(1)} s`);

export function MdUsage() {
  const phone = useMedia(PHONE);
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  const from = params.get("from") || undefined;
  const to = params.get("to") || undefined;

  const load = useCallback(async () => {
    try { setData(await getUsage(from, to)); setError(null); } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    }
  }, [from, to]);
  useEffect(() => { void load(); }, [load]);

  const t = data?.totals;
  const setRange = (f: string, tt: string) => setParams({ from: f, to: tt });

  return (
    <MdShell title="Usage" eyebrow={data ? `${data.label} · ${data.working_days} working days` : undefined}
      actions={data && (
        <div className="range-row">
          <label>From <input type="date" className="md-chip-input" value={data.from} max={data.to}
            onChange={(e) => e.target.value && setRange(e.target.value, data.to)} /></label>
          <label>To <input type="date" className="md-chip-input" value={data.to} min={data.from}
            onChange={(e) => e.target.value && setRange(data.from, e.target.value)} /></label>
        </div>
      )}>
      {error && <p className="error-text" role="alert">{error}</p>}
      {data && t && (
        <>
          <div className="stats stats-6">
            {[
              { label: "Both scans", value: pct(t.both_pct), sub: "of active people, per day" },
              { label: "First try", value: pct(t.first_try_pct), sub: `${t.first_try} of ${t.tries}` },
              { label: "Tap to receipt", value: secs(t.tap_to_receipt_ms), sub: "median" },
              { label: "No clock-out", value: String(t.missing_clock_out), sub: `in ${data.working_days} days` },
              { label: "Reasons sent", value: String(t.reasons), sub: `${t.reasons_approved} approved · ${t.reasons_rejected} rejected` },
              { label: "From paper", value: String(t.paper), sub: "times added" },
            ].map((s) => (
              <div key={s.label} className="stat">
                <span className="stat-label">{s.label}</span>
                <span className="stat-value">{s.value}</span>
                <span className="stat-sub">{s.sub}</span>
              </div>
            ))}
          </div>

          {data.days.length > 0 && (
            <section>
              <h2 className="group-title">Both scans, % per working day</h2>
              <div className="group" role="img" aria-label={`Both scans per day: ${data.days.map((d) => `${d.label} ${pct(d.both_pct)}`).join(", ")}`}>
                <div className="bars" aria-hidden="true">
                  {data.days.map((d) => (
                    <div key={d.date} className="bar-col">
                      <span className="bar-value">{d.both_pct ?? "--"}</span>
                      <div className="bar" style={{ height: `${Math.max(1, d.both_pct ?? 0) * 0.8}%` }} />
                    </div>
                  ))}
                </div>
                <div className="bar-labels" aria-hidden="true">
                  {data.days.map((d) => <span key={d.date}>{phone ? d.label.split(" ")[1] : d.label.replace(/^\w+ /, "")}</span>)}
                </div>
              </div>
            </section>
          )}

          <section>
            <h2 className="group-title">Failed scans by cause</h2>
            <div className="group">
              {data.failures.map((f) => (
                <div key={f.code} className="row"><span className="row-body"><span>{f.label}</span>
                  <span className="row-value mono">{f.count}</span></span></div>
              ))}
              {!data.failures.length && <p className="empty-note">No failed scans.</p>}
            </div>
          </section>

          <section>
            <h2 className="group-title">Per day</h2>
            {phone ? (
              <div className="group">
                {data.days.map((d) => (
                  <div key={d.date} className="row" style={{ minHeight: 60 }}>
                    <span className="row-body">
                      <span className="two-line">
                        <span style={{ fontWeight: 600 }}>{d.label}</span>
                        <span className="sub-note">{d.active} active · first try {pct(d.first_try_pct)} · {secs(d.tap_to_receipt_ms)}
                          {d.missing_clock_out ? ` · ${d.missing_clock_out} no clock-out` : ""}{d.reasons ? ` · ${d.reasons} reasons` : ""}</span>
                      </span>
                      <span className="mono" style={{ fontWeight: 700 }}>{pct(d.both_pct)}</span>
                    </span>
                  </div>
                ))}
                {!data.days.length && <p className="empty-note">No working days in this range.</p>}
              </div>
            ) : (
              <div className="group">
                <div className="md-table-head md-usage-cols">
                  <span>Day</span><span>Active</span><span>Both scans</span><span>First try</span><span>Tap to receipt</span>
                  <span>No clock-out</span><span>Reasons</span><span>From paper</span>
                </div>
                {data.days.map((d) => (
                  <div key={d.date} className="md-table-row md-usage-cols">
                    <span style={{ fontWeight: 600 }}>{d.label}</span><span>{d.active}</span><span>{pct(d.both_pct)}</span>
                    <span>{pct(d.first_try_pct)}</span><span>{secs(d.tap_to_receipt_ms)}</span>
                    <span>{d.missing_clock_out}</span><span>{d.reasons}</span><span>{d.paper}</span>
                  </div>
                ))}
                {!data.days.length && <p className="empty-note">No working days in this range.</p>}
              </div>
            )}
            <p className="group-footer">Both scans counts clock-ins and clock-outs made with the app; times from the paper
              sheet don't count. The same numbers: <span className="mono">python -m app.admin usage --from {data.from} --to {data.to}</span></p>
          </section>
        </>
      )}
    </MdShell>
  );
}
