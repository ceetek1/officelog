// System-style alert (centered, title + message + actions).
import { useEffect, useId, useRef, type ReactNode } from "react";

export interface AlertAction { label: string; onPress: () => void; bold?: boolean; cancel?: boolean; destructive?: boolean }

export function Alert({ title, message, actions, icon }: {
  title: string; message?: string; actions: AlertAction[]; icon?: ReactNode;
}) {
  const id = useId();
  const firstButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    firstButton.current?.focus();
    // Escape = the Cancel action, or the only action. Never a confirming one.
    const escape = actions.find((a) => a.cancel) || (actions.length === 1 ? actions[0] : undefined);
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && escape) escape.onPress(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [actions]);
  return (
    <div className="alert-backdrop">
      <div className="alert" role="alertdialog" aria-modal="true" aria-labelledby={`${id}-t`}
        aria-describedby={message ? `${id}-m` : undefined}>
        <div className="alert-body">
          {icon}
          <span id={`${id}-t`} className="alert-title">{title}</span>
          {message && <span id={`${id}-m`} className="alert-message">{message}</span>}
        </div>
        <div className="alert-actions">
          {actions.map((a, i) => (
            <button key={a.label} ref={i === 0 ? firstButton : undefined} type="button"
              className={`alert-action${a.bold ? " alert-action-bold" : ""}${a.destructive ? " alert-action-destructive" : ""}`} onClick={a.onPress}>
              {a.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
