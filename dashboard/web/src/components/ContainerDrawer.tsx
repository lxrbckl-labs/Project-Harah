// Slide-over drawer: a container's live logs + its CPU/mem history.
import { useEffect, useRef, useState } from 'react';
import { api, type ContainerHistoryResp } from '../api';

function MiniChart({ series }: { series: ContainerHistoryResp['series'] }) {
  const w = 560, h = 90, padT = 8, padB = 4, padL = 4, padR = 28;
  const n = series.length;
  if (n === 0) return <div className="chip" style={{ padding: '24px 0' }}>collecting samples…</div>;
  const pW = w - padL - padR, pH = h - padT - padB;
  const xi = (i: number) => (n <= 1 ? padL + pW / 2 : padL + (i / (n - 1)) * pW);
  const yi = (v: number) => padT + pH - (Math.max(0, Math.min(100, v)) / 100) * pH;
  const path = (key: 'cpu' | 'mem') => `M ${series.map((s, i) => `${xi(i).toFixed(1)},${yi(s[key]).toFixed(1)}`).join(' L ')}`;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: h }}>
      {[0, 50, 100].map(g => {
        const y = padT + pH - (g / 100) * pH;
        return <g key={g}><line x1={padL} y1={y} x2={w - padR} y2={y} stroke="rgba(255,255,255,0.06)" />
          <text x={w - padR + 4} y={y + 3} fontSize="9" fill="var(--faint)">{g}</text></g>;
      })}
      <path d={path('mem')} fill="none" stroke="var(--violet)" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
      <path d={path('cpu')} fill="none" stroke="var(--accent-2)" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export default function ContainerDrawer({ name, onClose }: { name: string | null; onClose: () => void }) {
  const [logs, setLogs] = useState('');
  const [hist, setHist] = useState<ContainerHistoryResp | null>(null);
  const [loading, setLoading] = useState(false);
  const logRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    if (!name) return;
    let alive = true;
    const load = async () => {
      setLoading(true);
      try { const r = await api.logs(name, 400); if (alive) setLogs(r.logs); } catch { /* */ }
      setLoading(false);
    };
    load();
    api.containerHistory(name, 360).then(h => { if (alive) setHist(h); }).catch(() => {});
    const t = setInterval(load, 5000);
    return () => { alive = false; clearInterval(t); };
  }, [name]);

  useEffect(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight; }, [logs]);

  if (!name) return null;
  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 50 }} />
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0, width: 'min(680px, 92vw)', zIndex: 51,
        background: 'var(--panel-solid)', backdropFilter: 'blur(24px)', borderLeft: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column', boxShadow: '-20px 0 60px -20px #000',
      }}>
        <div className="panel-head" style={{ padding: 20, marginBottom: 0, borderBottom: '1px solid var(--border)' }}>
          <div><h3 style={{ fontSize: 17 }}>{name}</h3><div className="sub">Logs &amp; resource history</div></div>
          <button className="btn" onClick={onClose}>✕ Close</button>
        </div>
        <div style={{ padding: 20, borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', gap: 16, marginBottom: 8, fontSize: 12.5 }}>
            <span><span style={{ display: 'inline-block', width: 9, height: 9, borderRadius: 2, background: 'var(--accent-2)', marginRight: 6 }} />CPU</span>
            <span><span style={{ display: 'inline-block', width: 9, height: 9, borderRadius: 2, background: 'var(--violet)', marginRight: 6 }} />Memory</span>
            <span className="chip" style={{ marginLeft: 'auto' }}>last 6h</span>
          </div>
          <MiniChart series={hist?.series ?? []} />
        </div>
        <div style={{ padding: '14px 20px 6px', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span className="chip">LOGS (tail 400){loading && <span className="spin" style={{ marginLeft: 8 }} />}</span>
        </div>
        <pre ref={logRef} style={{
          flex: 1, overflow: 'auto', margin: 0, padding: '0 20px 20px',
          fontFamily: 'ui-monospace, Menlo, monospace', fontSize: 11.5, lineHeight: 1.55,
          color: 'var(--muted)', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
        }}>{logs || 'No log output.'}</pre>
      </div>
    </>
  );
}
