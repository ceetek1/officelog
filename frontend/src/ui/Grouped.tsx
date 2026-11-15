// iOS inset grouped list: a white card of rows with hairline dividers.
import type { InputHTMLAttributes, ReactNode } from "react";

export function Group({ title, footer, children }: { title?: string; footer?: ReactNode; children: ReactNode }) {
  return (
    <section>
      {title && <h2 className="group-title">{title}</h2>}
      <div className="group">{children}</div>
      {footer && <p className="group-footer">{footer}</p>}
    </section>
  );
}

export function Row({ label, value, mono }: { label: ReactNode; value?: ReactNode; mono?: boolean }) {
  return (
    <div className="row">
      <span className="row-body">
        <span>{label}</span>
        {value !== undefined && <span className={`row-value${mono ? " mono" : ""}`}>{value}</span>}
      </span>
    </div>
  );
}

export function FieldRow({ label, ...input }: { label: string } & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="row">
      <span className="row-body">
        <span className="row-label">{label}</span>
        <input className="row-input" {...input} />
      </span>
    </label>
  );
}
