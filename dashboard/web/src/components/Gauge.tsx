// Circular progress ring (SVG). value is 0..100.
interface Props {
  value: number;
  label: string;
  sublabel?: string;
  size?: number;
}

function colorFor(v: number): string {
  if (v >= 85) return 'var(--bad)';
  if (v >= 65) return 'var(--warn)';
  return 'var(--accent-2)';
}

export default function Gauge({ value, label, sublabel, size = 120 }: Props) {
  const v = Math.max(0, Math.min(100, value));
  const stroke = 10;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const off = c * (1 - v / 100);
  const col = colorFor(v);
  return (
    <div className="ring" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke="rgba(255,255,255,0.07)" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke={col} strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={off}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: 'stroke-dashoffset .6s ease, stroke .3s' }} />
      </svg>
      <div className="center">
        <div>
          <div className="num">{Math.round(v)}<span style={{ fontSize: 14 }}>%</span></div>
          <div className="cap">{label}</div>
          {sublabel && <div className="cap" style={{ marginTop: 2, color: 'var(--faint)' }}>{sublabel}</div>}
        </div>
      </div>
    </div>
  );
}
