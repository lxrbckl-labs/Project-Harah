// Storage panel — boot disk + external drives with capacity/usage bars.
import { useEffect, useState, useCallback } from 'react';
import { api, fmtBytes, type StorageResp } from '../api';

export default function StoragePanel() {
  const [data, setData] = useState<StorageResp | null>(null);
  const load = useCallback(async () => { try { setData(await api.storage()); } catch { /* */ } }, []);
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [load]);

  const vols = data?.volumes ?? [];
  return (
    <div className="panel col-6">
      <div className="panel-head">
        <div><h3>Storage</h3><div className="sub">Boot disk &amp; external drives</div></div>
        <span className="chip">{vols.length} volumes</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
        {vols.map(v => {
          const bg = v.percent >= 85 ? 'var(--bad)'
            : v.percent >= 65 ? 'var(--warn)'
            : v.external ? 'linear-gradient(90deg,var(--violet),var(--accent-2))'
            : 'linear-gradient(90deg,var(--accent),var(--accent-2))';
          return (
            <div key={v.mount}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 7 }}>
                <span style={{ fontWeight: 650, fontSize: 13.5 }}>
                  {v.external ? '🔌 ' : '💽 '}{v.name}
                  <span className="chip" style={{ marginLeft: 8 }}>{v.external ? 'external' : 'internal'} · {v.fstype}</span>
                </span>
                <span style={{ fontSize: 12.5, color: 'var(--muted)', fontVariantNumeric: 'tabular-nums' }}>
                  {fmtBytes(v.used)} / {fmtBytes(v.total)}
                </span>
              </div>
              <div className="mini-bar" style={{ height: 9 }}><span style={{ width: `${v.percent}%`, background: bg }} /></div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
                <span className="chip">{v.percent}% used</span>
                <span className="chip">{fmtBytes(v.free)} free</span>
              </div>
            </div>
          );
        })}
        {vols.length === 0 && <div className="chip">No volumes detected.</div>}
      </div>
    </div>
  );
}
