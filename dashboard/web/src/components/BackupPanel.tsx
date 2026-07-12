// DB Backup panel — postgres containers, last backup, and a "Backup now" button.
import { useEffect, useState, useCallback } from 'react';
import { api, fmtBytes, type BackupsResp } from '../api';

function ago(ts?: number): string {
  if (!ts) return 'never';
  const s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export default function BackupPanel() {
  const [data, setData] = useState<BackupsResp | null>(null);
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const load = useCallback(async () => {
    try { setData(await api.backups()); } catch { /* */ }
  }, []);
  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  async function run(name: string) {
    setBusy(b => ({ ...b, [name]: true }));
    try { await api.backupNow(name); } catch { /* */ }
    setTimeout(load, 800);
    setBusy(b => ({ ...b, [name]: false }));
  }

  const dbs = data?.databases ?? [];
  return (
    <div className="panel col-6">
      <div className="panel-head">
        <div><h3>Database Backups</h3><div className="sub">pg_dump of Postgres containers</div></div>
        <span className="chip">{dbs.length} databases</span>
      </div>
      <div>
        {dbs.map(db => {
          const st = db.status?.state;
          const running = st === 'running' || busy[db.name];
          return (
            <div key={db.name} className="arm-row" style={{ alignItems: 'center' }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{db.name}</div>
                <div className="chip">
                  {db.last_backup
                    ? <>last {ago(db.last_backup.ts)} · {fmtBytes(db.last_backup.size)}</>
                    : 'no backup yet'}
                  {st === 'error' && <span style={{ color: 'var(--bad)' }}> · failed</span>}
                  {st === 'done' && <span style={{ color: 'var(--good)' }}> · ✓ done</span>}
                </div>
              </div>
              <button className="btn" disabled={running || db.state !== 'running'} onClick={() => run(db.name)}>
                {running ? <span className="spin" /> : 'Backup now'}
              </button>
            </div>
          );
        })}
        {dbs.length === 0 && <div className="chip">No Postgres containers found.</div>}
      </div>
      {data && <div className="chip" style={{ marginTop: 12 }}>→ {data.backup_dir}</div>}
    </div>
  );
}
