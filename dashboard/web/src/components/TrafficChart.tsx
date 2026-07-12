// Elaborated SVG traffic chart: gridlines, adaptive time/date axis, peak marker,
// and an interactive hover tooltip. Data points are {t: epoch-seconds, count}.
import { useEffect, useRef, useState, type MouseEvent } from 'react';

interface Point { t: number; count: number; }
interface Props { data: Point[]; bucketSeconds: number; height?: number; }

function fmtTick(t: number, bucketSeconds: number, spanDays: number): string {
  const d = new Date(t * 1000);
  if (bucketSeconds >= 86400 || spanDays > 2)
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
function fmtFull(t: number, bucketSeconds: number): string {
  const d = new Date(t * 1000);
  if (bucketSeconds >= 86400)
    return d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
  return d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export default function TrafficChart({ data, bucketSeconds, height = 160 }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(700);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    setW(el.clientWidth);
    const ro = new ResizeObserver((es) => setW(es[0].contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const n = data.length;
  if (n === 0) {
    return <div ref={wrapRef} className="chip" style={{ padding: '34px 0' }}>no traffic in this range</div>;
  }

  const H = height;
  const padT = 16, padB = 24, padL = 6, padR = 26;
  const plotW = Math.max(1, w - padL - padR);
  const plotH = Math.max(1, H - padT - padB);
  const counts = data.map(d => d.count);
  const max = Math.max(1, ...counts);
  const span = data[n - 1].t - data[0].t;
  const spanDays = span / 86400;

  const xi = (i: number) => (n <= 1 ? padL + plotW / 2 : padL + (i / (n - 1)) * plotW);
  const yi = (v: number) => padT + plotH - (v / max) * plotH;

  const linePts = data.map((d, i) => `${xi(i).toFixed(1)},${yi(d.count).toFixed(1)}`);
  const line = `M ${linePts.join(' L ')}`;
  const baseY = (padT + plotH).toFixed(1);
  const area = `M ${xi(0).toFixed(1)},${baseY} L ${linePts.join(' L ')} L ${xi(n - 1).toFixed(1)},${baseY} Z`;

  const grid = [0, 0.5, 1];
  const nTicks = Math.min(6, n);
  const tickIdx = nTicks <= 1 ? [0]
    : Array.from({ length: nTicks }, (_, k) => Math.round((k * (n - 1)) / (nTicks - 1)));
  let peakI = 0;
  for (let i = 1; i < n; i++) if (counts[i] > counts[peakI]) peakI = i;

  const onMove = (e: MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const frac = (e.clientX - rect.left - padL) / plotW;
    setHover(Math.max(0, Math.min(n - 1, Math.round(frac * (n - 1)))));
  };

  const hv = hover != null ? data[hover] : null;

  return (
    <div ref={wrapRef} style={{ position: 'relative', width: '100%' }}
      onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
      <svg width={w} height={H} style={{ display: 'block' }}>
        <defs>
          <linearGradient id="tg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.42" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {grid.map((g, k) => {
          const y = padT + plotH - g * plotH;
          return (
            <g key={k}>
              <line x1={padL} y1={y} x2={w - padR} y2={y} stroke="rgba(255,255,255,0.06)" strokeWidth={1} />
              <text x={w - padR + 4} y={y + 3} fontSize="10" fill="var(--faint)">{Math.round(g * max)}</text>
            </g>
          );
        })}
        <path d={area} fill="url(#tg)" />
        <path d={line} fill="none" stroke="var(--accent-2)" strokeWidth={2}
          strokeLinejoin="round" strokeLinecap="round" />
        {counts[peakI] > 0 && (
          <circle cx={xi(peakI)} cy={yi(counts[peakI])} r={3} fill="var(--accent-2)" />
        )}
        {tickIdx.map((i, k) => (
          <text key={k} x={xi(i)} y={H - 6} fontSize="10" fill="var(--faint)"
            textAnchor={k === 0 ? 'start' : k === tickIdx.length - 1 ? 'end' : 'middle'}>
            {fmtTick(data[i].t, bucketSeconds, spanDays)}
          </text>
        ))}
        {hv && (
          <g>
            <line x1={xi(hover as number)} y1={padT} x2={xi(hover as number)} y2={padT + plotH}
              stroke="rgba(255,255,255,0.28)" strokeWidth={1} strokeDasharray="3 3" />
            <circle cx={xi(hover as number)} cy={yi(hv.count)} r={4} fill="#fff"
              stroke="var(--accent-2)" strokeWidth={2} />
          </g>
        )}
      </svg>
      {hv && (
        <div style={{
          position: 'absolute',
          left: Math.min(Math.max(xi(hover as number), 64), w - 64),
          top: -4, transform: 'translateX(-50%)',
          background: 'rgba(10,14,26,0.94)', border: '1px solid var(--border-strong)',
          borderRadius: 8, padding: '6px 10px', pointerEvents: 'none',
          fontSize: 12, whiteSpace: 'nowrap', boxShadow: '0 8px 24px -10px #000',
        }}>
          <div style={{ fontWeight: 700 }}>{hv.count.toLocaleString()} req</div>
          <div className="chip">{fmtFull(hv.t, bucketSeconds)}</div>
        </div>
      )}
    </div>
  );
}
