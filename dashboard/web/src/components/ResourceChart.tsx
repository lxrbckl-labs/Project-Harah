// Multi-series host-usage chart: CPU / Memory / Disk (%) over time.
// Fixed 0–100 y-axis, legend, gridlines, adaptive time axis, hover tooltip.
import { useEffect, useRef, useState, type MouseEvent } from 'react';
import type { ResSample } from '../api';

interface Props { data: ResSample[]; height?: number; }

const SERIES = [
  { key: 'cpu', label: 'CPU', color: 'var(--accent-2)' },
  { key: 'mem', label: 'Memory', color: 'var(--violet)' },
  { key: 'disk', label: 'Disk', color: 'var(--good)' },
] as const;

function fmtTick(t: number, spanDays: number): string {
  const d = new Date(t * 1000);
  if (spanDays > 2) return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
function fmtFull(t: number): string {
  return new Date(t * 1000).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export default function ResourceChart({ data, height = 200 }: Props) {
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
  const H = height;
  const padT = 10, padB = 24, padL = 6, padR = 30;
  const plotW = Math.max(1, w - padL - padR);
  const plotH = Math.max(1, H - padT - padB);

  const xi = (i: number) => (n <= 1 ? padL + plotW / 2 : padL + (i / (n - 1)) * plotW);
  const yi = (v: number) => padT + plotH - (Math.max(0, Math.min(100, v)) / 100) * plotH;
  const span = n > 0 ? data[n - 1].t - data[0].t : 0;
  const spanDays = span / 86400;

  const grid = [0, 25, 50, 75, 100];
  const nTicks = Math.min(6, n);
  const tickIdx = nTicks <= 1 ? [0]
    : Array.from({ length: nTicks }, (_, k) => Math.round((k * (n - 1)) / (nTicks - 1)));

  const onMove = (e: MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const frac = (e.clientX - rect.left - padL) / plotW;
    setHover(Math.max(0, Math.min(n - 1, Math.round(frac * (n - 1)))));
  };
  const hv = hover != null ? data[hover] : null;

  return (
    <div>
      <div style={{ display: 'flex', gap: 18, marginBottom: 10 }}>
        {SERIES.map(s => (
          <div key={s.key} style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12.5 }}>
            <span style={{ width: 10, height: 10, borderRadius: 3, background: s.color }} />
            <span style={{ color: 'var(--muted)' }}>{s.label}</span>
            <span style={{ fontWeight: 700 }}>{n ? `${data[n - 1][s.key]}%` : '—'}</span>
          </div>
        ))}
      </div>

      {n === 0 ? (
        <div ref={wrapRef} className="chip" style={{ padding: '46px 0' }}>
          collecting samples… (history builds as the backend runs)
        </div>
      ) : (
        <div ref={wrapRef} style={{ position: 'relative', width: '100%' }}
          onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
          <svg width={w} height={H} style={{ display: 'block' }}>
            {grid.map((g, k) => {
              const y = padT + plotH - (g / 100) * plotH;
              return (
                <g key={k}>
                  <line x1={padL} y1={y} x2={w - padR} y2={y} stroke="rgba(255,255,255,0.055)" strokeWidth={1} />
                  <text x={w - padR + 4} y={y + 3} fontSize="10" fill="var(--faint)">{g}</text>
                </g>
              );
            })}
            {SERIES.map(s => {
              const pts = data.map((d, i) => `${xi(i).toFixed(1)},${yi(d[s.key]).toFixed(1)}`);
              return (
                <path key={s.key} d={`M ${pts.join(' L ')}`} fill="none" stroke={s.color}
                  strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" opacity={0.95} />
              );
            })}
            {tickIdx.map((i, k) => (
              <text key={k} x={xi(i)} y={H - 6} fontSize="10" fill="var(--faint)"
                textAnchor={k === 0 ? 'start' : k === tickIdx.length - 1 ? 'end' : 'middle'}>
                {fmtTick(data[i].t, spanDays)}
              </text>
            ))}
            {hv && (
              <g>
                <line x1={xi(hover as number)} y1={padT} x2={xi(hover as number)} y2={padT + plotH}
                  stroke="rgba(255,255,255,0.28)" strokeWidth={1} strokeDasharray="3 3" />
                {SERIES.map(s => (
                  <circle key={s.key} cx={xi(hover as number)} cy={yi(hv[s.key])} r={3.5}
                    fill="#0b0f1a" stroke={s.color} strokeWidth={2} />
                ))}
              </g>
            )}
          </svg>
          {hv && (
            <div style={{
              position: 'absolute', left: Math.min(Math.max(xi(hover as number), 80), w - 80),
              top: -4, transform: 'translateX(-50%)', background: 'rgba(10,14,26,0.94)',
              border: '1px solid var(--border-strong)', borderRadius: 8, padding: '7px 11px',
              pointerEvents: 'none', fontSize: 12, whiteSpace: 'nowrap', boxShadow: '0 8px 24px -10px #000',
            }}>
              <div className="chip" style={{ marginBottom: 4 }}>{fmtFull(hv.t)}</div>
              {SERIES.map(s => (
                <div key={s.key} style={{ display: 'flex', justifyContent: 'space-between', gap: 14 }}>
                  <span style={{ color: 'var(--muted)' }}>
                    <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 2, background: s.color, marginRight: 6 }} />
                    {s.label}
                  </span>
                  <span style={{ fontWeight: 700 }}>{hv[s.key]}%</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
