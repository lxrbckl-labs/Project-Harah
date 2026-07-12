// Hardware — the Mac mini (M4 Pro, 48GB) this server runs on, as a single card.
import type { HostStats } from '../api';
import { fmtBytes } from '../api';

const SPECS: [string, string][] = [
  ['Chip', 'Apple M4 Pro'],
  ['CPU', '12‑core (8P + 4E)'],
  ['GPU', '16‑core'],
  ['Memory', '48 GB unified · 273 GB/s'],
  ['Storage', '512 GB – 8 TB SSD'],
  ['Thunderbolt', '3× Thunderbolt 5'],
  ['Wireless', 'Wi‑Fi 6E · Bluetooth 5.3'],
];

export default function HardwareView({ host }: { host?: HostStats }) {
  return (
    <div className="panel col-4" style={{ display: 'flex', flexDirection: 'column' }}>
      <div className="panel-head"><div><h3>Hardware</h3><div className="sub">Apple M4 Pro Mac mini (2024)</div></div></div>

      <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 18 }}>
        <img src="/mac-mini.png" alt="Apple Mac mini (2024)" loading="lazy"
          style={{ width: 116, height: 78, objectFit: 'contain', flex: 'none', filter: 'drop-shadow(0 12px 16px rgba(0,0,0,0.55))' }} />
        <div>
          <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: '-0.02em' }}>Mac mini</div>
          <div style={{ color: 'var(--muted)', fontSize: 13, marginTop: 2 }}>M4 Pro · 48 GB</div>
        </div>
      </div>

      <div>
        {SPECS.map(([k, v]) => (
          <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: '7px 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
            <span style={{ color: 'var(--muted)', fontSize: 12.5 }}>{k}</span>
            <span style={{ fontSize: 12.5, fontWeight: 600, textAlign: 'right' }}>{v}</span>
          </div>
        ))}
      </div>

      <div className="chip" style={{ marginTop: 14 }}>
        DETECTED: {host?.cpu_count ?? '—'} cores · {host ? fmtBytes(host.mem.total) : '—'} RAM · {host ? fmtBytes(host.disk.total) : '—'} disk
      </div>

      <a className="btn start" href="https://www.apple.com/mac-mini/" target="_blank" rel="noopener noreferrer"
        style={{ marginTop: 16, textAlign: 'center', textDecoration: 'none' }}>
        View on Apple ↗
      </a>
    </div>
  );
}
