interface Bar { label: string; value: number }

/** Dependency-free SVG histogram. */
export function BarChart({ data, height = 170 }: { data: Bar[]; height?: number }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  const barWidth = 100 / (data.length * 1.6);
  const gap = barWidth * 0.6;

  return (
    <svg width="100%" height={height} role="img" aria-label="Cluster size distribution">
      {data.map((bar, index) => {
        const h = (bar.value / max) * (height - 34);
        const x = index * (barWidth + gap) + gap / 2;
        return (
          <g key={bar.label}>
            <rect
              x={`${x}%`}
              y={height - 22 - h}
              width={`${barWidth}%`}
              height={Math.max(h, 2)}
              rx={4}
              fill="var(--accent-1)"
              opacity={0.35 + 0.65 * (bar.value / max)}
            />
            <text
              x={`${x + barWidth / 2}%`}
              y={height - 6}
              textAnchor="middle"
              fill="var(--text-dim)"
              fontSize="10"
            >
              {bar.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
