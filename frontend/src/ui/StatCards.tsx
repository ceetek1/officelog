export interface Stat { label: string; value: number | string; color?: string }

/** Three small number cards in a row. */
export function StatCards({ stats }: { stats: Stat[] }) {
  return (
    <div className="stats">
      {stats.map((s) => (
        <div key={s.label} className="stat">
          <span className="stat-label">{s.label}</span>
          <span className="stat-value" style={s.color ? { color: s.color } : undefined}>{s.value}</span>
        </div>
      ))}
    </div>
  );
}
