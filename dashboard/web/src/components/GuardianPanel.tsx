// Auto-Defense panel — detects brute-force/flooding from the Caddy logs and,
// for armed containers only (while the master switch is on), auto-stops them.
import type { GuardianResp } from '../api';

const CRITICAL = new Set(['vaultwarden', 'immich_server', 'immich_postgres']);

function ago(ts: number): string {
  const s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

interface Props {
  g: GuardianResp | null;
  onToggle: (enabled: boolean) => void;
  onArm: (container: string, armed: boolean) => void;
}

export default function GuardianPanel({ g, onToggle, onArm }: Props) {
  const enabled = g?.enabled ?? false;
  const armed = new Set(g?.armed ?? []);
  const threats = g?.threats ?? [];
  const actions = g?.actions ?? [];
  // containers Caddy fronts (unique), plus any already-armed
  const containers = Array.from(new Set([...Object.values(g?.mapping ?? {}), ...(g?.armed ?? [])])).sort();

  return (
    <div className="panel col-12">
      <div className="panel-head">
        <div>
          <h3>Auto‑Defense{' '}
            <span className={`guard-status ${enabled ? 'on' : 'off'}`} style={{ marginLeft: 6 }}>
              <span className="sev-dot" style={{ background: enabled ? 'var(--good)' : 'var(--faint)' }} />
              {enabled ? 'ARMED' : 'MONITORING'}
            </span>
          </h3>
          <div className="sub">
            Watches Caddy logs for brute‑force / flooding.{' '}
            {enabled
              ? 'Armed containers auto‑stop when attacked.'
              : 'Detection only — nothing will be stopped.'}
          </div>
        </div>
        <button className={`switch ${enabled ? 'on' : ''}`} onClick={() => onToggle(!enabled)} aria-label="toggle auto-defense">
          <span className="knob" />
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr', gap: 26 }}>
        {/* live threats */}
        <div>
          <div className="chip" style={{ marginBottom: 10 }}>
            LIVE THREATS · last {g?.window_sec ?? 60}s
          </div>
          {threats.length === 0 && <div className="chip">No attacks detected. All quiet.</div>}
          {threats.map((t, i) => {
            const willAct = enabled && t.container && armed.has(t.container) && (!g?.ignore_private || !t.private);
            return (
              <div key={i} className={`threat-row ${t.severity === 'high' ? '' : 'elevated'}`}>
                <span className="sev-dot" style={{ background: t.severity === 'high' ? 'var(--bad)' : 'var(--warn)' }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13.5, fontWeight: 600 }}>{t.host}
                    {t.container && <span className="chip" style={{ marginLeft: 8 }}>→ {t.container}</span>}
                  </div>
                  <div className="chip" style={{ marginTop: 2 }}>
                    <span className="code" style={{ fontSize: 11 }}>{t.top_ip}</span> · {t.top_ip_count} req · {t.auth_fails} auth‑fails
                    {t.private && <span style={{ color: 'var(--faint)' }}> · LAN/local</span>}
                  </div>
                </div>
                <span className="chip" style={{ color: willAct ? 'var(--bad)' : 'var(--muted)', whiteSpace: 'nowrap' }}>
                  {willAct ? 'will auto‑stop' : t.container && armed.has(t.container) ? 'armed (LAN ignored)' : 'monitoring'}
                </span>
              </div>
            );
          })}
        </div>

        {/* arm controls */}
        <div>
          <div className="chip" style={{ marginBottom: 10 }}>ARM CONTAINERS FOR AUTO‑STOP</div>
          <div style={{ maxHeight: 220, overflowY: 'auto', paddingRight: 4 }}>
            {containers.map(c => {
              const isCritical = CRITICAL.has(c);
              const on = armed.has(c);
              return (
                <div className="arm-row" key={c}>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c}</div>
                    {isCritical && <div className="chip" style={{ color: 'var(--warn)' }}>⚠ critical — stopping locks you out too</div>}
                  </div>
                  <button className={`switch sm ${on ? 'on' : ''}`} onClick={() => onArm(c, !on)} aria-label={`arm ${c}`}>
                    <span className="knob" />
                  </button>
                </div>
              );
            })}
            {containers.length === 0 && <div className="chip">No Caddy‑fronted containers mapped.</div>}
          </div>

          {actions.length > 0 && (
            <>
              <div className="chip" style={{ margin: '14px 0 8px' }}>RECENT AUTO‑STOPS</div>
              {actions.map((a, i) => (
                <div key={i} style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 5 }}>
                  <span style={{ color: 'var(--bad)', fontWeight: 600 }}>{a.container}</span> stopped {ago(a.ts)} — {a.reason}
                </div>
              ))}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
