// Face ID / fingerprint via WebAuthn passkeys.
import { startAuthentication, startRegistration } from "@simplewebauthn/browser";

export class FaceIdCancelled extends Error {}
/** The browser refused because the request didn't come straight from a tap. */
export class FaceIdNeedsTap extends Error {}

function wrap(e: unknown): never {
  const name = e && typeof e === "object" && "name" in e ? String((e as { name: unknown }).name) : "";
  const cause = e && typeof e === "object" && "cause" in e ? (e as { cause?: { name?: string } }).cause : undefined;
  const n = (cause && cause.name) || name;
  if (n === "NotAllowedError" || n === "AbortError") throw new FaceIdCancelled("Face ID was cancelled.");
  if (n === "SecurityError") throw new FaceIdNeedsTap("Tap to use Face ID.");
  throw e instanceof Error ? e : new Error("Face ID didn't work.");
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function faceIdRegister(options: any) {
  try { return await startRegistration({ optionsJSON: options }); } catch (e) { return wrap(e); }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function faceIdConfirm(options: any) {
  try { return await startAuthentication({ optionsJSON: options }); } catch (e) { return wrap(e); }
}

export function faceIdAvailable(): boolean {
  return typeof window !== "undefined" && !!window.PublicKeyCredential;
}
