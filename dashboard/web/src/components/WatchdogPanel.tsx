// Estate health, and the record of what Harah did about it unattended.
// If something went down at 03:00 and Harah restarted it, this is where Alex
// sees that without reading a log file.
import { useEffect, useState, useCallback } from 'react';
import { api, type WatchdogResp, type Incident } from '../api';

function ago(ts?: number | null): string {
  if (!ts) return 'never';
  const s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

const OUTCOME_COLOR: Record<string, string> = {
  fixed: 'var(--good)',
  escalated: 'var(--warn)',
};

function IncidentRow({ i }: { i: Incident }) {
  return (
    <div className="arm-row" style={{ alignItems: 'center' }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {i.target}
          <span style={{ color: OUTCOME_COLOR[i.outcome] ?? 'var(--faint)', marginLeft: 8, fontSize: 11, textTransform: 'uppercase' }}>
            {i.outcome === 'fixed' ? '✓ fixed' : i.outcome}
          </span>
        </div>
        <div className="chip">
          {ago(i.ts)}{i.action && i.action !== 'none' ? ` · ${i.action}` : ''}
        </div>
      </div>
    </div>
  );
}

export default function WatchdogPanel() {
  const [d, setD] = useState<WatchdogResp | null>(null);
  const load = useCallback(async () => {
    try { setD(await api.watchdog()); } catch { /* */ }
  }, []);
  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [load]);

  if (!d) return null;
  const targets = d.targets ?? [];
  const down = targets.filter(t => !t.ok && !t.known_bad);
  const knownBad = targets.filter(t => t.known_bad);
  const incidents = d.incidents ?? [];

  return (
    <div className="panel col-6">
      <div className="panel-head">
        <div>
          <h3>Estate Health</h3>
          <div className="sub">watched every 10 min · Harah repairs without asking</div>
        </div>
        <span className="chip">last check {ago(d.last_run)}</span>
      </div>

      <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', marginBottom: 12 }}>
        <div>
          <div style={{ fontSize: 20, fontWeight: 700, color: down.length ? 'var(--bad)' : 'var(--good)' }}>
            {targets.length - down.length}/{targets.length}
          </div>
          <div className="chip" style={{ textTransform: 'uppercase', letterSpacing: '.06em' }}>serving</div>
        </div>
        <div>
          <div style={{ fontSize: 20, fontWeight: 700, color: incidents.length ? 'var(--warn)' : 'var(--faint)' }}>
            {incidents.length}
          </div>
          <div className="chip" style={{ textTransform: 'uppercase', letterSpacing: '.06em' }}>incidents</div>
        </div>
      </div>

      {down.length > 0 ? (
        down.map(t => (
          <div key={t.name} className="arm-row">
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--bad)' }}>{t.name}</div>
              <div className="chip">{t.detail}</div>
            </div>
          </div>
        ))
      ) : (
        <div className="chip" style={{ color: 'var(--good)' }}>
          ● everything serving
        </div>
      )}

      {incidents.length > 0 && (
        <>
          <div className="chip" style={{ margin: '12px 0 4px' }}>Recent autonomous action</div>
          {incidents.slice(0, 5).map((i, n) => <IncidentRow key={`${i.target}-${i.ts}-${n}`} i={i} />)}
        </>
      )}

      {knownBad.length > 0 && (
        <div className="chip" style={{ marginTop: 12 }}>
          known-bad, excluded from alerting: {knownBad.map(t => t.name).join(', ')}
        </div>
      )}
    </div>
  );
}
