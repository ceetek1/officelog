// Spec §7 (Nigeria Data Protection Act 2023): what is collected, why, who sees it, how long, contact.
import { Sheet } from "../../ui/Sheets";

export function PrivacyNotice({ company, onClose }: { company: string; onClose: () => void }) {
  const who = company || "your employer";
  return (
    <Sheet title="Privacy" onCancel={onClose} cancelLabel="Close">
      <div className="sheet-body prose">
        <h3>What we collect</h3>
        <p>Your name, the times you clock in and out, a passkey that ties this app to this phone, and the
          internet address (IP) your phone used for each clock-in or clock-out.</p>
        <h3>What we don't collect</h3>
        <p>No location, no photos. Face ID or fingerprint is checked by your phone; your face and
          fingerprint never leave it.</p>
        <h3>Why</h3>
        <p>To record attendance at {who} during a trial of this system, and to see if the system is easy
          to use.</p>
        <h3>Who sees it</h3>
        <p>You see your own times. The manager and the managing director see everyone's.</p>
        <h3>How long we keep it</h3>
        <p>For the length of the trial. Then it is deleted, unless {who} decides to keep using the system.</p>
        <h3>Questions or requests</h3>
        <p>Ask your manager or the managing director. You can ask to see or correct what is held about you.</p>
      </div>
    </Sheet>
  );
}
