// Hardware tab — the Mac mini (M4 Pro, 48GB) this server runs on.
import type { HostStats } from '../api';
import { fmtBytes } from '../api';

const SPECS: { group: string; items: [string, string][] }[] = [
  {
    group: 'Chip',
    items: [
      ['Processor', 'Apple M4 Pro'],
      ['CPU', '12‑core (8 performance + 4 efficiency)'],
      ['GPU', '16‑core'],
      ['Neural Engine', '16‑core'],
    ],
  },
  {
    group: 'Memory & Storage',
    items: [
      ['Unified memory', '48 GB'],
      ['Memory bandwidth', '273 GB/s'],
      ['Storage', '512 GB – 8 TB SSD'],
    ],
  },
  {
    group: 'Connectivity',
    items: [
      ['Thunderbolt', '3× Thunderbolt 5 (120 Gb/s)'],
      ['Front ports', '2× USB‑C (10 Gb/s), headphone'],
      ['HDMI', '1× (8K @ 60Hz)'],
      ['Ethernet', 'Gigabit (configurable 10GbE)'],
      ['Wireless', 'Wi‑Fi 6E · Bluetooth 5.3'],
    ],
  },
  {
    group: 'Physical',
    items: [
      ['Dimensions', '5.0 × 12.7 × 12.7 cm'],
      ['Weight', '0.73 kg (1.6 lb)'],
      ['Released', '2024'],
    ],
  },
];

export default function HardwareView({ host }: { host?: HostStats }) {
  return (
    <div className="grid">
      {/* device card */}
      <div className="panel col-5" style={{ display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'grid', placeItems: 'center', padding: '18px 0 22px' }}>
          <svg width="200" height="150" viewBox="0 0 200 150">
            <defs>
              <linearGradient id="mm" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#3a4260" />
                <stop offset="100%" stopColor="#1a1f34" />
              </linearGradient>
              <radialGradient id="mmg" cx="50%" cy="30%" r="70%">
                <stop offset="0%" stopColor="rgba(109,139,255,0.5)" />
                <stop offset="100%" stopColor="rgba(109,139,255,0)" />
              </radialGradient>
            </defs>
            <ellipse cx="100" cy="126" rx="78" ry="10" fill="rgba(0,0,0,0.35)" />
            <rect x="34" y="40" width="132" height="80" rx="18" fill="url(#mm)"
              stroke="rgba(255,255,255,0.14)" strokeWidth="1" />
            <rect x="34" y="40" width="132" height="80" rx="18" fill="url(#mmg)" />
            <circle cx="100" cy="80" r="12" fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth="1.5" />
            <circle cx="100" cy="80" r="3" fill="rgba(255,255,255,0.5)" />
          </svg>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-0.02em' }}>Mac mini</div>
          <div style={{ color: 'var(--muted)', marginTop: 2 }}>Apple M4 Pro · 48 GB</div>
        </div>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'center', margin: '20px 0 6px', flexWrap: 'wrap' }}>
          <span className="hw-badge">M4 Pro</span>
          <span className="hw-badge">12‑core CPU</span>
          <span className="hw-badge">48 GB RAM</span>
        </div>
        <a className="btn start" href="https://www.apple.com/mac-mini/" target="_blank" rel="noopener noreferrer"
          style={{ marginTop: 'auto', textAlign: 'center', textDecoration: 'none' }}>
          View on Apple ↗
        </a>
      </div>

      {/* spec sheet */}
      <div className="panel col-7">
        <div className="panel-head"><div><h3>Technical Specifications</h3><div className="sub">Apple M4 Pro Mac mini (2024)</div></div></div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '22px 34px' }}>
          {SPECS.map(sec => (
            <div key={sec.group}>
              <div className="chip" style={{ marginBottom: 10, letterSpacing: '0.06em' }}>{sec.group.toUpperCase()}</div>
              {sec.items.map(([k, v]) => (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 14, padding: '6px 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                  <span style={{ color: 'var(--muted)', fontSize: 13 }}>{k}</span>
                  <span style={{ fontSize: 13, fontWeight: 600, textAlign: 'right' }}>{v}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* detected live */}
      <div className="panel col-12">
        <div className="panel-head"><div><h3>Detected on this machine</h3><div className="sub">Live, from the running server</div></div></div>
        <div style={{ display: 'flex', gap: 40, flexWrap: 'wrap' }}>
          <div><div className="chip">CPU CORES</div><div style={{ fontSize: 26, fontWeight: 800 }}>{host?.cpu_count ?? '—'}</div></div>
          <div><div className="chip">TOTAL RAM</div><div style={{ fontSize: 26, fontWeight: 800 }}>{host ? fmtBytes(host.mem.total) : '—'}</div></div>
          <div><div className="chip">DISK</div><div style={{ fontSize: 26, fontWeight: 800 }}>{host ? fmtBytes(host.disk.total) : '—'}</div></div>
          <div><div className="chip">LOAD AVG</div><div style={{ fontSize: 26, fontWeight: 800 }}>{host?.load_avg[0] ?? '—'}</div></div>
        </div>
      </div>
    </div>
  );
}
