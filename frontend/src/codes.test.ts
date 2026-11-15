import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { daySecret, qrContent, qrWindow, typedCode, typedWindow } from "./codes";

const data = JSON.parse(
  readFileSync(new URL("../../tests/fixtures/code_vectors.json", import.meta.url), "utf8"),
);

const hex = (b: Uint8Array) => Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");

describe("codes.ts matches app/codes.py", () => {
  for (const v of data.vectors) {
    it(`${v.work_date} @ ${v.unix}`, async () => {
      const s = await daySecret(new TextEncoder().encode(data.master), v.work_date);
      expect(hex(s)).toBe(v.day_secret_hex);
      expect(qrWindow(v.unix)).toBe(v.qr_window);
      expect(await qrContent(s, v.qr_window)).toBe(v.qr);
      expect(typedWindow(v.unix)).toBe(v.typed_window);
      expect(await typedCode(s, v.typed_window)).toBe(v.typed);
    });
  }
});
