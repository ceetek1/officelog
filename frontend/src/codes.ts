// Rotating clock-in codes: a browser copy of app/codes.py (decision D2).
//
// Not used yet: today the server makes the codes and the TV only displays them. This file exists
// so a future offline mode can let the TV make codes itself with the SAME algorithm, QR format and
// scan API. tests/fixtures/code_vectors.json keeps it identical to the Python version
// (see codes.test.ts). Read app/codes.py for the full description.

export const QR_STEP = 5;
export const TYPED_STEP = 30;
export const TYPED_SLACK = 5;
export const QR_PREFIX = "ATT1";

const enc = new TextEncoder();

async function hmac(key: Uint8Array, data: Uint8Array): Promise<Uint8Array> {
  const k = await crypto.subtle.importKey("raw", key as BufferSource, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return new Uint8Array(await crypto.subtle.sign("HMAC", k, data as BufferSource));
}

export function daySecret(master: Uint8Array, workDate: string): Promise<Uint8Array> {
  return hmac(master, enc.encode("kiosk:" + workDate));
}

export function purposeKey(secret: Uint8Array, purpose: "qr" | "typed"): Promise<Uint8Array> {
  return hmac(secret, enc.encode("purpose:" + purpose));
}

export async function code6(key: Uint8Array, window: number): Promise<string> {
  const counter = new Uint8Array(8);
  // 8-byte big-endian; windows fit in 2^53, so split into high and low 32 bits.
  const high = Math.floor(window / 0x100000000);
  const low = window >>> 0;
  new DataView(counter.buffer).setUint32(0, high);
  new DataView(counter.buffer).setUint32(4, low);
  const mac = await hmac(key, counter);
  const offset = mac[mac.length - 1] & 0x0f;
  const value = new DataView(mac.buffer, mac.byteOffset).getUint32(offset) & 0x7fffffff;
  return String(value % 1000000).padStart(6, "0");
}

export const qrWindow = (unixSeconds: number) => Math.floor(unixSeconds / QR_STEP);
export const typedWindow = (unixSeconds: number) => Math.floor(unixSeconds / TYPED_STEP);

export async function qrContent(secret: Uint8Array, window: number): Promise<string> {
  return `${QR_PREFIX}.${window}.${await code6(await purposeKey(secret, "qr"), window)}`;
}

export async function typedCode(secret: Uint8Array, window: number): Promise<string> {
  return code6(await purposeKey(secret, "typed"), window);
}
