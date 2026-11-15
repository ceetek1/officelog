// Entrance TV welcome board (Prototype B "Smart TV · welcome board"; spec §4.2, §5; decision D2).
// Runs unattended in a smart TV's built-in browser: no interaction, polls every second, shows
// "Connection lost" after 10 s without the server, reloads itself if stuck or when a new version
// is deployed.
import QRCode from "qrcode";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError, kioskCode, kioskPair, type KioskCode } from "../../api";
import { PaperIcon } from "../../ui/icons";
import "./tv.css";

const POLL_MS = 1000;
const LOST_AFTER_MS = 10_000;
const STUCK_AFTER_MS = 30_000;
const W = 1920;
const H = 1080;

function useStageScale() {
  const [scale, setScale] = useState(1);
  useEffect(() => {
    const fit = () => setScale(Math.min(window.innerWidth / W, window.innerHeight / H));
    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, []);
  return scale;
}

/** Tiny shifts every minute so a static image doesn't burn into the screen. */
function useDrift() {
  const [d, setD] = useState({ x: 0, y: 0 });
  useEffect(() => {
    const id = setInterval(() => setD({ x: Math.round(Math.random() * 8 - 4), y: Math.round(Math.random() * 8 - 4) }), 60_000);
    return () => clearInterval(id);
  }, []);
  return d;
}

function Stage({ children }: { children: ReactNode }) {
  const scale = useStageScale();
  const drift = useDrift();
  const left = (window.innerWidth - W * scale) / 2 + drift.x;
  const top = (window.innerHeight - H * scale) / 2 + drift.y;
  const t = `translate(${left}px, ${top}px) scale(${scale})`;
  return (
    <div className="tv-viewport">
      <div className="tv-stage" style={{ transform: t, WebkitTransform: t }}>{children}</div>
    </div>
  );
}

function QrSvg({ text }: { text: string }) {
  const qr = QRCode.create(text, { errorCorrectionLevel: "M" });
  const n = qr.modules.size;
  const q = 2; // quiet zone, in modules
  let d = "";
  for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (qr.modules.get(r, c)) d += `M${c + q},${r + q}h1v1h-1z`;
  return (
    <svg className="tv-qr" viewBox={`0 0 ${n + 2 * q} ${n + 2 * q}`} shapeRendering="crispEdges"
      role="img" aria-label="Clock-in QR code, changes every 5 seconds">
      <rect width={n + 2 * q} height={n + 2 * q} fill="#fff" />
      <path d={d} fill="#171717" />
    </svg>
  );
}

/** Largest size (up to 220 px) at which the name fits the left column (about 1000 px). */
function nameSize(name: string): number {
  return Math.max(110, Math.min(220, Math.floor(1000 / (name.length * 0.6))));
}

function withTimeout<T>(p: Promise<T>, ms: number): Promise<T> {
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new ApiError(0, "timeout", "timeout")), ms);
    p.then((v) => { clearTimeout(t); resolve(v); }, (e) => { clearTimeout(t); reject(e); });
  });
}

export function Tv() {
  const [data, setData] = useState<KioskCode | null>(null);
  const [lost, setLost] = useState(false);
  const [unpaired, setUnpaired] = useState(false);
  const lastOk = useRef(Date.now());
  const lastTick = useRef(Date.now());
  const version = useRef<string | null>(null);
  const started = useRef(Date.now());

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      lastTick.current = Date.now();
      try {
        const d = await withTimeout(kioskCode(), 4000);
        if (!alive) return;
        if (version.current === null) version.current = d.version;
        else if (d.version !== version.current) { window.location.reload(); return; }
        lastOk.current = Date.now();
        setData(d);
        setLost(false);
        setUnpaired(false);
        // Once a day, early morning, start fresh (only while the server is reachable).
        const h = new Date().getHours();
        if (h === 4 && Date.now() - started.current > 2 * 3600_000) { window.location.reload(); return; }
      } catch (e) {
        if (!alive) return;
        if (e instanceof ApiError && e.code === "kiosk_not_paired") setUnpaired(true);
        if (Date.now() - lastOk.current > LOST_AFTER_MS) setLost(true);
      }
      timer = setTimeout(poll, POLL_MS);
    }
    void poll();
    // Watchdog: if the poll loop itself has stopped, reload the page.
    const watchdog = setInterval(() => {
      if (Date.now() - lastTick.current > STUCK_AFTER_MS) window.location.reload();
    }, 5000);
    return () => { alive = false; clearTimeout(timer); clearInterval(watchdog); };
  }, []);

  if (unpaired) {
    return (
      <Stage>
        <div className="tv-message">
          <h1>This TV isn't set up</h1>
          <p>Ask the manager for the TV setup link, and open it in this TV's web browser.</p>
        </div>
      </Stage>
    );
  }
  if (!data) return <Stage>{null}</Stage>;

  const [latest, ...rest] = data.recent;
  const earlier = rest.slice(0, 4);
  const barPct = Math.max(0, Math.min(100, (data.typed_ms_left / data.typed_step_ms) * 100));

  return (
    <Stage>
      <div className="tv-inner">
        <section className="tv-left" aria-live="polite">
          <header className="tv-header">
            <span className="tv-greet">{data.greeting}</span>
            <span className="tv-clock">{data.date} · <span className="tv-mono">{data.time}</span></span>
          </header>
          <div className="tv-hero">
            {lost && <span className="tv-offline-pill" role="status">Connection lost · scans paused</span>}
            {latest ? (
              <>
                <span className="tv-hello">{latest.kind === "in" ? "Welcome," : "Goodbye,"}</span>
                <span className="tv-name" style={{ fontSize: nameSize(latest.name) }}>{latest.name}</span>
                <span className="tv-time tv-mono">{latest.time}</span>
              </>
            ) : (
              <>
                <span className="tv-headline">Scan with<br />your phone</span>
                <span className="tv-sub">Your phone shows your time.</span>
              </>
            )}
          </div>
          {earlier.length > 0 && (
            <div>
              <div className="tv-earlier-title">Earlier</div>
              <ul className="tv-chips">
                {earlier.map((e) => (
                  <li key={e.id} className="tv-chip">
                    <span className="tv-chip-name">{e.name}</span>
                    <span className="tv-chip-time tv-mono">{e.time}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <p className="tv-paper"><PaperIcon />No phone? Write your time on the paper sheet.</p>
        </section>
        <section className="tv-card" aria-label="Clock in code">
          {lost ? (
            <>
              <span className="tv-paused">Connection lost<br />Scans paused</span>
              <span className="tv-paused-sub">Write your time on the paper sheet.</span>
            </>
          ) : (
            <>
              <span className="tv-card-title">Scan to clock<br />in or out</span>
              <QrSvg text={data.qr} />
              <div className="tv-typed">
                <div className="tv-typed-label">Camera not working? Type</div>
                <div className="tv-typed-code tv-mono">{data.typed}</div>
                <div className="tv-bar" aria-hidden="true"><div className="tv-bar-fill" style={{ width: `${barPct}%` }} /></div>
              </div>
            </>
          )}
        </section>
      </div>
    </Stage>
  );
}

export function TvPair() {
  const { token = "" } = useParams();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    kioskPair(token)
      .then(() => navigate("/tv", { replace: true }))
      .catch((e) => setError(e instanceof Error ? e.message : "Something went wrong."));
  }, [token, navigate]);
  return (
    <Stage>
      <div className="tv-message">
        <h1>{error ? "Can't set up this TV" : "Setting up this TV…"}</h1>
        {error && <p>{error}</p>}
      </div>
    </Stage>
  );
}
