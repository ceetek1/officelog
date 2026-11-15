// A QR code drawn as SVG (the `qrcode` package only builds the matrix; nothing leaves the phone).
import QRCode from "qrcode";

export function QrCode({ text, label, size = 188 }: { text: string; label: string; size?: number }) {
  const qr = QRCode.create(text, { errorCorrectionLevel: "M" });
  const n = qr.modules.size;
  const q = 2; // quiet zone, in modules
  let d = "";
  for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (qr.modules.get(r, c)) d += `M${c + q},${r + q}h1v1h-1z`;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${n + 2 * q} ${n + 2 * q}`} shapeRendering="crispEdges"
      role="img" aria-label={label} style={{ display: "block", maxWidth: "100%", height: "auto" }}>
      <rect width={n + 2 * q} height={n + 2 * q} fill="#fff" />
      <path d={d} fill="#171717" />
    </svg>
  );
}
