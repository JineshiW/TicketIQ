import { colorForKey } from "@/lib/format";

interface Slice { label: string; value: number }

/** Dependency-free SVG donut. */
export function DonutChart({ data, size = 170 }: { data: Slice[]; size?: number }) {
  const total = data.reduce((sum, d) => sum + d.value, 0);
  const radius = size / 2 - 14;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <div className="row" style={{ gap: 22, flexWrap: "wrap" }}>
      <svg width={size} height={size} role="img" aria-label="Patterns by type">
        <g transform={`translate(${size / 2} ${size / 2}) rotate(-90)`}>
          <circle r={radius} fill="none" stroke="var(--surface-3)" strokeWidth={16} />
          {total > 0 &&
            data.map((slice) => {
              const length = (slice.value / total) * circumference;
              const dash = `${length} ${circumference - length}`;
              const el = (
                <circle
                  key={slice.label}
                  r={radius}
                  fill="none"
                  stroke={colorForKey(slice.label)}
                  strokeWidth={16}
                  strokeDasharray={dash}
                  strokeDashoffset={-offset}
                />
              );
              offset += length;
              return el;
            })}
        </g>
        <text x="50%" y="48%" textAnchor="middle" fill="var(--text)" fontSize="22" fontWeight="700">
          {total}
        </text>
        <text x="50%" y="60%" textAnchor="middle" fill="var(--text-dim)" fontSize="10">
          Total
        </text>
      </svg>

      <ul className="stack" style={{ gap: 8, listStyle: "none", padding: 0, margin: 0 }}>
        {data.map((slice) => (
          <li key={slice.label} className="legend__item">
            <span className="legend__dot" style={{ background: colorForKey(slice.label) }} />
            <span className="small muted">
              {slice.label} · {slice.value}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
