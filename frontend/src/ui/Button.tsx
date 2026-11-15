import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "plain";

export function Button({ variant = "primary", className = "", ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return <button type="button" className={`btn btn-${variant} ${className}`} {...rest} />;
}
