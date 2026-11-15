import { useEffect, useState } from "react";

/** True while the media query matches, e.g. useMedia("(max-width: 760px)") for phones. */
export function useMedia(query: string): boolean {
  const [on, setOn] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const m = window.matchMedia(query);
    const change = () => setOn(m.matches);
    change();
    m.addEventListener("change", change);
    return () => m.removeEventListener("change", change);
  }, [query]);
  return on;
}

export const PHONE = "(max-width: 760px)";
