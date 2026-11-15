import type { ReactNode } from "react";

export interface SheetAction { label: string; onPress: () => void; destructive?: boolean }

/** iOS action sheet: a list of choices plus Cancel, from the bottom, with an optional heading. */
export function ActionSheet({ actions, onCancel, title, message }: {
  actions: SheetAction[]; onCancel: () => void; title?: string; message?: string;
}) {
  return (
    <div className="sheet-backdrop" onClick={onCancel}>
      <div className="action-sheet" role="dialog" aria-modal="true" aria-label={title}
        onClick={(e) => e.stopPropagation()}>
        <div className="action-group">
          {(title || message) && (
            <div className="action-head">
              {title && <span className="action-title">{title}</span>}
              {message && <span className="action-message">{message}</span>}
            </div>
          )}
          {actions.map((a) => (
            <button key={a.label} type="button" className={`action-item${a.destructive ? " action-destructive" : ""}`}
              onClick={a.onPress}>{a.label}</button>
          ))}
        </div>
        <div className="action-group">
          <button type="button" className="action-item action-cancel" onClick={onCancel}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

/** iOS page sheet with a Cancel / title / (optional) Done bar. */
export function Sheet({ title, onCancel, cancelLabel = "Cancel", right, children }: {
  title: string; onCancel: () => void; cancelLabel?: string; right?: ReactNode; children: ReactNode;
}) {
  return (
    <div className="sheet-backdrop">
      <div className="sheet" role="dialog" aria-modal="true" aria-label={title}>
        <span className="sheet-grabber" aria-hidden="true" />
        <div className="navbar" style={{ height: 50 }}>
          <button type="button" className="btn btn-plain" onClick={onCancel}>{cancelLabel}</button>
          <span className="navbar-title">{title}</span>
          <span style={{ position: "relative", zIndex: 1 }}>{right}</span>
        </div>
        {children}
      </div>
    </div>
  );
}
