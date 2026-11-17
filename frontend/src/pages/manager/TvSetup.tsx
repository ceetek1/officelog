// Manager · Entrance TV. Status, last seen, remove the TV,
// and a single-use setup code to type on the TV (the TV can't scan a code).
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, createTvLink, getTvs, removeTv, type Tv, type TvLink } from "../../api";
import { Alert } from "../../ui/Alert";
import { Button } from "../../ui/Button";
import { Group, Row } from "../../ui/Grouped";
import { ChevronLeft } from "../../ui/icons";
import { Pill } from "../../ui/Pill";
import { QrCode } from "../../ui/QrCode";
import { TabBar } from "../../ui/TabBar";
import { copyText } from "./InviteCard";
import { TV_TONE } from "./People";

export function TvSetup() {
  const navigate = useNavigate();
  const [tvs, setTvs] = useState<Tv[] | null>(null);
  const [scans, setScans] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [link, setLink] = useState<TvLink | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState<Tv | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    try {
      const d = await getTvs();
      setTvs(d.tvs);
      setScans(d.scans_today);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    }
  }, []);
  useEffect(() => {
    void load();
    // While a setup code is waiting, watch for the TV to pair.
    const id = setInterval(() => { if (document.visibilityState === "visible") void load(); }, 5000);
    return () => clearInterval(id);
  }, [load]);

  const paired = (tvs || []).filter((t) => t.status !== "waiting");
  const waiting = (tvs || []).filter((t) => t.status === "waiting");
  // The code just made is shown until that TV pairs.
  const shown = link && waiting.some((t) => t.id === link.id) ? link : null;

  async function makeLink() {
    setBusy(true);
    try { setLink(await createTvLink()); setCopied(false); await load(); } catch (e) {
      setFailed(e instanceof ApiError ? e.message : "Something went wrong. Try again.");
    } finally { setBusy(false); }
  }
  async function remove(t: Tv) {
    setConfirm(null);
    try { await removeTv(t.id); } catch (e) {
      setFailed(e instanceof ApiError ? e.message : "Something went wrong. Try again.");
    }
    if (link?.id === t.id) setLink(null);
    void load();
  }

  return (
    <div className="phone">
      <div className="navbar">
        <button type="button" className="btn btn-plain" onClick={() => navigate("/people")}><ChevronLeft />People</button>
        <span className="navbar-title">Entrance TV</span>
        <span />
      </div>
      <main className="phone-main">
        {error && (
          <div className="stack-16">
            <p className="error-text" role="alert">{error}</p>
            <Button variant="secondary" onClick={() => void load()}>Try Again</Button>
          </div>
        )}
        {tvs && paired.length === 0 && !shown && (
          <Group><Row label="Status" value={<Pill tone="wait">Not set up</Pill>} /></Group>
        )}
        {paired.map((t, i) => (
          <div key={t.id} className="stack-16">
            <Group title={paired.length > 1 ? `TV ${i + 1}` : undefined}>
              <Row label="Status" value={<Pill tone={TV_TONE[t.status]}>{t.label}</Pill>} />
              <Row label="Set up" value={t.set_up} />
              <Row label="Last seen" value={t.last_seen || "Never"} />
              {i === 0 && <Row label="Scans today" value={String(scans)} />}
            </Group>
            <Button className="btn-destructive-soft" onClick={() => setConfirm(t)}>Remove This TV</Button>
          </div>
        ))}

        {shown ? (
          <section className="invite-card" aria-label="TV setup code">
            <h2>Type this on the TV</h2>
            <span className="setup-code" aria-label={shown.code.split("").join(" ")}>{shown.code}</span>
            <p className="status-note">On the TV's web browser, open<br /><strong className="mono">{shown.tv_page.replace(/^https?:\/\//, "")}</strong><br />
              and type the code. It works once, until {shown.expires}.</p>
            <Button variant="secondary" onClick={() => void copyText(shown.link).then(setCopied)}>
              {copied ? "Copied" : "Copy Full Link"}</Button>
            <details style={{ width: "100%" }}>
              <summary className="status-note" style={{ cursor: "pointer", minHeight: 44, display: "flex", alignItems: "center", justifyContent: "center" }}>
                Using a tablet with a camera?</summary>
              <div style={{ display: "flex", justifyContent: "center", paddingTop: 8 }}>
                <QrCode text={shown.link} label="TV setup QR code" size={160} />
              </div>
            </details>
            <span className="status-note" role="status">Waiting for the TV…</span>
          </section>
        ) : (
          <>
            <Group title="Set up a TV">
              <Row label={<><span className="step-num">1</span>On the TV, open the web browser</>} />
              <Row label={<><span className="step-num">2</span>Go to the attendance page /tv</>} />
              <Row label={<><span className="step-num">3</span>Type the setup code</>} />
              <Row label={<><span className="step-num">4</span>Set the TV to switch on each morning</>} />
            </Group>
            <Button disabled={busy} onClick={() => void makeLink()}>{busy ? "Making a code…" : "Get a Setup Code"}</Button>
          </>
        )}
        {waiting.length > 0 && (
          <Group title="Setup codes not used yet">
            {waiting.map((t) => (
              <div key={t.id} className="row">
                <span className="row-body">
                  <span className="two-line"><span>Setup code</span><span className="sub-note">Works until {t.link_expires}</span></span>
                  <button type="button" className="btn btn-plain" style={{ color: "#dc2626" }}
                    onClick={() => void remove(t)}>Cancel Code</button>
                </span>
              </div>
            ))}
          </Group>
        )}
      </main>
      <TabBar role="manager" />

      {confirm && (
        <Alert title="Remove this TV?"
          message="It stops showing the clock-in code at once. To use it again, set it up with a new code."
          actions={[{ label: "Cancel", cancel: true, onPress: () => setConfirm(null) },
                    { label: "Remove", bold: true, destructive: true, onPress: () => void remove(confirm) }]} />
      )}
      {failed && <Alert title="Didn't Work" message={failed} actions={[{ label: "OK", onPress: () => setFailed(null) }]} />}
    </div>
  );
}
