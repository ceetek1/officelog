import { ClockIcon } from "./icons";

export function AppIcon({ size = 72 }: { size?: number }) {
  return (
    <span className="app-icon" style={{ width: size, height: size, borderRadius: size / 4 }}>
      <ClockIcon size={Math.round(size * 0.56)} />
    </span>
  );
}
