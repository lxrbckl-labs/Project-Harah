// Lightweight SVG area chart for the per-minute request series.
interface Props {
  data: number[];
  height?: number;
}

export default function TrafficChart({ data, height = 90 }: Props) {
  const w = 600;
  const h = height;
  const pad = 4;
  const n = data.length;
  const max = Math.max(1, ...data);

  if (n === 0) return <div className="chip" style={{ padding: '20px 0' }}>no traffic data</div>;

  const x = (i: number) => (n === 1 ? w / 2 : pad + (i * (w - pad * 2)) / (n - 1));
  const y = (v: number) => h - pad - (v / max) * (h - pad * 2);

  const pts = data.map((v, i) => `${x(i)},${y(v)}`);
  const line = `M ${pts.join(' L ')}`;
  const area = `M ${x(0)},${h} L ${pts.join(' L ')} L ${x(n - 1)},${h} Z`;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ width: '100%', height }}>
      <defs>
        <linearGradient id="tg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.45" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill="url(#tg)" />
      <path d={line} fill="none" stroke="var(--accent-2)" strokeWidth={2}
        vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
    </svg>
  );
}
