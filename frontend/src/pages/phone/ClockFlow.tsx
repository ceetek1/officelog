// Scan the TV code (or type it) → Face ID → receipt. Spec §4.2, decisions D1 and D2.
// Prototype B boards "5 · Scan TV code", "6 · Receipt".
import QrScanner from "qr-scanner";
import { useEffect, useRef, useState } from "react";
import { ApiError, clockFinish, clockStart, type Challenge, type Kind, type Method, type ReasonType, type Receipt } from "../../api";
import { faceIdConfirm, FaceIdCancelled } from "../../faceid";
import { worked } from "../../format";
import { Alert, type AlertAction } from "../../ui/Alert";
import { Button } from "../../ui/Button";
import { CheckIcon, DeleteIcon, FaceIdIcon, KeypadIcon } from "../../ui/icons";
import { Sheet } from "../../ui/Sheets";

type Stage = "scan" | "typing" | "checking" | "faceid" | "tap" | "receipt";

interface Props { kind: Kind; confirm: boolean; t0: number; onClose: () => void; onAddReason: (t: ReasonType) => void }

export function ClockFlow({ kind, confirm: confirmed, t0, onClose, onAddReason }: Props) {
  const [stage, setStage] = useState<Stage>("scan");
  const [message, setMessage] = useState<string | null>(null);
  const [typedError, setTypedError] = useState<string | null>(null);
  const [digits, setDigits] = useState("");
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [alert, setAlert] = useState<{ title: string; message?: string; actions: AlertAction[] } | null>(null);
  const [pending, setPending] = useState<Challenge | null>(null);
  const busy = useRef(false);
  const confirmRef = useRef(confirmed);
  const video = useRef<HTMLVideoElement>(null);
  const scanner = useRef<QrScanner | null>(null);
  const label = kind === "in" ? "Clock In" : "Clock Out";

  // Camera: runs while the scan stage is showing.
  useEffect(() => {
    if (stage !== "scan" || !video.current) return;
    const s = new QrScanner(video.current, (r) => onDecode(r.data), {
      preferredCamera: "environment", maxScansPerSecond: 8, returnDetailedScanResult: true,
      highlightScanRegion: false, highlightCodeOutline: false,
    });
    scanner.current = s;
    s.start().catch(() => setMessage("The camera isn't available. Allow the camera for this app, or type the code."));
    return () => { s.stop(); s.destroy(); scanner.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage]);

  function onDecode(text: string) {
    if (busy.current) return;
    if (!text.startsWith("ATT1.")) { setMessage("That isn't the attendance code. Point at the code on the TV."); return; }
    void submit("qr", text);
  }

  function back(to: Stage, msg: string | null) {
    busy.current = false;
    setPending(null);
    setMessage(to === "scan" ? msg : null);
    setTypedError(to === "typing" ? msg : null);
    if (to === "typing") setDigits("");
    setStage(to);
  }

  async function submit(method: Method, code: string) {
    if (busy.current) return;
    busy.current = true;
    setStage("checking");
    let ch: Challenge;
    try {
      ch = await clockStart(kind, method, code, confirmRef.current);
    } catch (e) {
      const from: Stage = method === "typed" ? "typing" : "scan";
      if (!(e instanceof ApiError)) return back(from, "Something went wrong. Try again.");
      if (e.code === "stale_code" || e.code === "not_our_code" || e.code === "offline") return back(from, e.message);
      if (e.code === "confirm_needed") {
        busy.current = false;
        setStage(from);
        setAlert({ title: "Clock Out Now?", message: e.message, actions: [
          { label: "Cancel", cancel: true, onPress: () => { setAlert(null); onClose(); } },
          { label: "Clock Out", bold: true, onPress: () => { setAlert(null); confirmRef.current = true; back(from, "Scan the code again."); } },
        ] });
        return;
      }
      busy.current = false;
      setAlert({ title: e.code === "phone_not_registered" ? "Phone Not Registered" : "Can't " + label, message: e.message,
        actions: [{ label: "OK", bold: true, onPress: () => { setAlert(null); onClose(); } }] });
      return;
    }
    await withFaceId(ch);
  }

  async function withFaceId(ch: Challenge) {
    setPending(ch);
    setStage("faceid");
    let credential;
    try {
      credential = await faceIdConfirm(ch.options);
    } catch (e) {
      // Cancelled, or the browser wants a direct tap first: offer a button.
      setStage("tap");
      if (!(e instanceof FaceIdCancelled)) setMessage(e instanceof Error ? e.message : null);
      return;
    }
    setStage("checking");
    try {
      const r = await clockFinish(ch.challenge_id, credential, Math.max(0, Date.now() - t0));
      setReceipt(r);
      setStage("receipt");
      busy.current = false;
    } catch (e) {
      if (e instanceof ApiError && e.code.startsWith("already_clocked")) {
        setAlert({ title: "Already Recorded", message: e.message,
          actions: [{ label: "OK", bold: true, onPress: () => { setAlert(null); onClose(); } }] });
        return;
      }
      back("scan", e instanceof Error ? e.message : "Something went wrong. Scan again.");
    }
  }

  function press(d: string) {
    if (busy.current) return;
    setTypedError(null);
    const next = (digits + d).slice(0, 6);
    setDigits(next);
    if (next.length === 6) void submit("typed", next);
  }

  if (stage === "receipt" && receipt) return <ReceiptScreen r={receipt} onDone={onClose} onAddReason={onAddReason} />;

  return (
    <div className="scanner">
      <div className="navbar">
        <button type="button" className="btn btn-plain" onClick={onClose}>Cancel</button>
        <span className="navbar-title">{label}</span>
      </div>
      <main className="scanner-main">
        <div className="scanner-frame">
          {/* The camera feed. Muted + playsInline are needed on iPhone. */}
          <video ref={video} muted playsInline aria-label="Camera" />
          <span className="scanner-corner scanner-corner-tl" aria-hidden="true" />
          <span className="scanner-corner scanner-corner-tr" aria-hidden="true" />
          <span className="scanner-corner scanner-corner-bl" aria-hidden="true" />
          <span className="scanner-corner scanner-corner-br" aria-hidden="true" />
        </div>
        <p className={`scanner-msg${message ? " scanner-error" : ""}`} role={message ? "alert" : undefined}>
          {message || "Point at the code on the TV"}
        </p>
      </main>
      <footer className="scanner-footer">
        <Button className="btn-glass" onClick={() => { setDigits(""); setTypedError(null); setStage("typing"); }}>
          <KeypadIcon size={20} /><span>Type Code Instead</span>
        </Button>
      </footer>

      {(stage === "typing" || (stage === "checking" && digits.length === 6)) && (
        <Sheet title="Type the Code" onCancel={() => back("scan", null)}>
          <p style={{ margin: "6px 24px 0", textAlign: "center", color: typedError ? "var(--bad-fg)" : "var(--text-2)" }}
            role={typedError ? "alert" : undefined}>
            {typedError || "The 6 numbers under the QR code"}
          </p>
          <div className="code-boxes" aria-label={`Code: ${digits.split("").join(" ") || "empty"}`}>
            {Array.from({ length: 6 }, (_, i) => (
              <span key={i} className={`code-box${i === digits.length ? " code-box-active" : ""}`} aria-hidden="true">
                {digits[i] || ""}
              </span>
            ))}
          </div>
          <div className="keypad">
            {["1", "2", "3", "4", "5", "6", "7", "8", "9"].map((d) => (
              <button key={d} type="button" className="key" onClick={() => press(d)}>{d}</button>
            ))}
            <span className="key key-blank" aria-hidden="true" />
            <button type="button" className="key" onClick={() => press("0")}>0</button>
            <button type="button" className="key key-fn" aria-label="Delete" onClick={() => setDigits(digits.slice(0, -1))}>
              <DeleteIcon />
            </button>
          </div>
        </Sheet>
      )}

      {(stage === "checking" || stage === "faceid") && (
        <div className="busy-overlay" role="status">
          <div className="busy-card"><FaceIdIcon size={64} /><span>{stage === "faceid" ? "Face ID" : "Checking…"}</span></div>
        </div>
      )}

      {stage === "tap" && pending && (
        <Sheet title={label} onCancel={() => back("scan", null)}>
          <div className="sheet-body" style={{ alignItems: "center", textAlign: "center" }}>
            <span style={{ color: "var(--primary)", display: "flex" }}><FaceIdIcon size={72} /></span>
            <p className="subtitle">Confirm it's you with Face ID.</p>
            {message && <p className="error-text">{message}</p>}
            <Button onClick={() => void withFaceId(pending)}>{label} with Face ID</Button>
          </div>
        </Sheet>
      )}

      {alert && <Alert title={alert.title} message={alert.message} actions={alert.actions} />}
    </div>
  );
}

function ReceiptScreen({ r, onDone, onAddReason }: { r: Receipt; onDone: () => void; onAddReason: (t: ReasonType) => void }) {
  const needs: ReasonType | null = r.kind === "in" && r.late_minutes !== null ? "late"
    : r.kind === "out" && r.left_early_minutes !== null ? "left_early" : null;
  return (
    <div className="scanner receipt">
      <main className="center-screen" role="status" style={{ padding: "0 24px", gap: 24 }}>
        <span className="receipt-badge" aria-hidden="true"><CheckIcon /></span>
        <div className="stack-16" style={{ gap: 4, alignItems: "center" }}>
          <h1 className="receipt-title">{r.kind === "in" ? "Clocked In" : "Clocked Out"}</h1>
          <span className="receipt-time">{r.time}</span>
          <span className="subtitle">{r.date}</span>
        </div>
        {r.kind === "in" && r.working_day && (r.late_minutes === null
          ? <span className="pill pill-ok pill-lg">On time</span>
          : <span className="pill pill-warn pill-lg">{r.late_minutes} min late</span>)}
        {r.kind === "out" && (
          <span className="subtitle">{worked(r.worked_minutes)} worked
            {r.left_early_minutes !== null && <> · <span className="word-warn">left {r.left_early_minutes} min early</span></>}</span>
        )}
      </main>
      <footer className="phone-footer" style={{ width: "100%", maxWidth: 520, margin: "0 auto", gap: 6 }}>
        <Button onClick={onDone} autoFocus>Done</Button>
        {needs && <Button variant="plain" style={{ width: "100%", fontWeight: 600 }} onClick={() => onAddReason(needs)}>Add a Reason</Button>}
      </footer>
    </div>
  );
}
