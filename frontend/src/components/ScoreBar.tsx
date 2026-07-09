// src/components/ScoreBar.tsx — Animated per-signal score bar

interface ScoreBarProps {
  label: string;
  value: number; // 0–1
  color: string; // Tailwind color class or hex
  icon?: string;
}

export function ScoreBar({ label, value, color, icon }: ScoreBarProps) {
  const pct = Math.round(value * 100);

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted flex items-center gap-1">
          {icon && <span>{icon}</span>}
          {label}
        </span>
        <span className="font-mono font-medium" style={{ color }}>
          {pct}%
        </span>
      </div>
      <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}
