// The invite: QR code, "single use · expires …",
// Share Link and Copy Link. Used after adding a person and after resetting a phone.
import { useState } from "react";
import type { Invite } from "../../api";
import { firstName } from "../../format";
import { Button } from "../../ui/Button";
import { ShareIcon } from "../../ui/icons";
import { Pill } from "../../ui/Pill";
import { QrCode } from "../../ui/QrCode";

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

export function InviteCard({ invite, note }: { invite: Invite; note?: string }) {
  const [copied, setCopied] = useState<"yes" | "no" | null>(null);
  const first = firstName(invite.name);
  const canShare = typeof navigator !== "undefined" && typeof navigator.share === "function";

  async function share() {
    try {
      await navigator.share({ title: "Attendance invite", text: `${first}, open this on your own phone to set up Face ID:`, url: invite.link });
    } catch {
      // The share sheet was closed: nothing to do.
    }
  }
  async function copy() {
    setCopied((await copyText(invite.link)) ? "yes" : "no");
  }

  return (
    <>
      <section className="invite-card" aria-label={`Invite for ${first}`}>
        <h2>Invite for {first}</h2>
        <QrCode text={invite.link} label={`Invite QR code for ${first}`} />
        <Pill tone="wait">Single use · expires {invite.expires}</Pill>
        <p className="status-note">{note || `${first} scans this with their own phone's camera, or opens the link you send.`}</p>
        <span className="invite-link">{invite.link}</span>
      </section>
      <div className="stack-16" style={{ gap: 8 }}>
        {canShare && <Button onClick={() => void share()}><ShareIcon size={22} /><span>Share Link</span></Button>}
        <Button variant={canShare ? "secondary" : "primary"} onClick={() => void copy()}>
          {copied === "yes" ? "Copied" : "Copy Link"}
        </Button>
        {copied === "no" && <p className="error-text" role="alert">Couldn't copy. Press and hold the link above to copy it.</p>}
      </div>
    </>
  );
}
