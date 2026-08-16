// Security alerts panel — open Dependabot alerts and the grooming cadence they
// drive. Grooming only ever sees dependabot *PRs*; this covers the alerts that
// have no PR behind them (no version-update config, or no fix published yet).
import { useEffect, useState, useCallback } from 'react';
import { api, type AlertsResp, type AlertItem, type AlertRepo, type ResolverResp } from '../api';

const CADENCE_LABEL: Record<string, string> = {
  '6h': 'every 6h', '12h': 'every 12h', daily: 'daily 05:30',
};

/** How often the resolver runs. Each pass is a full agent session doing real
 *  migration work, and a merge here deploys within ~5 min — so the backend
 *  allowlists these choices and floors them at 6h. */
function ResolverControl() {
  const [r, setR] = useState<ResolverResp | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setR(await api.resolver()); } catch { /* */ }
  }, []);
  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [load]);

  async function pick(choice: string) {
    setBusy(choice); setErr(null);
    try { setR(await api.setResolverCadence(choice)); }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(null); }
  }

  async function trigger(mode: 'run' | 'review') {
    setBusy(mode); setErr(null);
    try {
      setR(await api.runResolver(mode));
      // A real run lasts hours; poll faster while it's live so the state shows.
      setTimeout(load, 3000);
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(null); }
  }

  if (!r) return null;
  const choices = r.choices?.length ? r.choices : ['6h', '12h', 'daily'];
  return (
    <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid rgba(255,255,255,0.07)' }}>
      <div className="chip" style={{ marginBottom: 6 }}>
        Resolver — how often Harah does the fixing
        {r.running && <span style={{ color: 'var(--good)' }}> · running now</span>}
        {r.last_end && !r.running && <span> · last run {r.last_end.slice(11, 16)}</span>}
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {choices.map(c => {
          const active = r.label === c || r.cadence === c;
          return (
            <button key={c} className="btn" onClick={() => pick(c)} disabled={busy !== null}
              style={{
                fontSize: 11, padding: '4px 10px', cursor: 'pointer', opacity: busy && busy !== c ? 0.5 : 1,
                borderColor: active ? 'var(--good)' : undefined,
                color: active ? 'var(--good)' : undefined,
              }}>
              {busy === c ? '…' : CADENCE_LABEL[c] ?? c}
            </button>
          );
        })}
      </div>
      <div className="chip" style={{ margin: '10px 0 6px' }}>Trigger a pass now</div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        <button className="btn" onClick={() => trigger('review')}
          disabled={busy !== null || r.running}
          title="Read-only: reports what it would do. No branches, pushes, merges or comments."
          style={{ fontSize: 11, padding: '4px 10px', cursor: r.running ? 'not-allowed' : 'pointer' }}>
          {busy === 'review' ? '…' : 'Review only'}
        </button>
        <button className="btn" onClick={() => trigger('run')}
          disabled={busy !== null || r.running}
          title="Real run: loops until the board is clear. Merges deploy within ~5 min."
          style={{
            fontSize: 11, padding: '4px 10px', cursor: r.running ? 'not-allowed' : 'pointer',
            borderColor: 'var(--warn)', color: 'var(--warn)',
          }}>
          {busy === 'run' ? '…' : 'Resolve now'}
        </button>
        {r.running && (
          <span className="chip" style={{ alignSelf: 'center', color: 'var(--good)' }}>
            {r.run_mode === 'review' ? 'review' : 'run'} in progress — merges deploy in ~5 min
          </span>
        )}
      </div>
      {err && <div className="err" style={{ marginTop: 6 }}>{err}</div>}
    </div>
  );
}

function ago(ts?: number | null): string {
  if (!ts) return 'never';
  const s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

const SEV_COLOR: Record<string, string> = {
  critical: 'var(--bad)',
  high: 'var(--warn)',
  medium: 'var(--faint)',
  low: 'var(--faint)',
};

function cadenceLabel(c?: AlertsResp['cadence']): string {
  if (!c) return 'grooming: unknown';
  if (c.interval_seconds == null) return 'grooming: daily 04:30';
  return `grooming: every ${Math.round(c.interval_seconds / 3600)}h`;
}

function Tally({ totals }: { totals: AlertsResp['totals'] }) {
  const cells: Array<[string, number]> = [
    ['critical', totals.critical], ['high', totals.high],
    ['medium', totals.medium], ['low', totals.low],
  ];
  return (
    <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', marginBottom: 12 }}>
      {cells.map(([k, v]) => (
        <div key={k}>
          <div style={{ fontSize: 20, fontWeight: 700, color: v > 0 ? SEV_COLOR[k] : 'var(--faint)' }}>{v}</div>
          <div className="chip" style={{ textTransform: 'uppercase', letterSpacing: '.06em' }}>{k}</div>
        </div>
      ))}
    </div>
  );
}

function NewRow({ item }: { item: AlertItem }) {
  return (
    <div className="arm-row" style={{ alignItems: 'center' }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          <a href={item.url} target="_blank" rel="noreferrer" style={{ color: 'inherit', textDecoration: 'none' }}>
            {item.repo.split('/')[1]}#{item.number}
          </a>
          <span style={{ color: SEV_COLOR[item.severity] ?? 'var(--faint)', marginLeft: 8, fontSize: 11, textTransform: 'uppercase' }}>
            {item.severity}
          </span>
        </div>
        <div className="chip" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '100%' }}>
          {item.package}{item.summary ? ` · ${item.summary}` : ''}
        </div>
      </div>
    </div>
  );
}

function RepoRow({ r }: { r: AlertRepo }) {
  return (
    <div className="arm-row" style={{ alignItems: 'center' }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          <a href={`https://github.com/${r.repo}/security/dependabot`} target="_blank" rel="noreferrer"
             style={{ color: 'inherit', textDecoration: 'none' }}>
            {r.repo.split('/')[1]}
          </a>
        </div>
        <div className="chip">
          {r.critical > 0 && <span style={{ color: 'var(--bad)' }}>{r.critical} critical · </span>}
          {r.high > 0 && <span style={{ color: 'var(--warn)' }}>{r.high} high · </span>}
          {r.open} open
        </div>
      </div>
    </div>
  );
}

export default function AlertsPanel() {
  const [data, setData] = useState<AlertsResp | null>(null);
  const load = useCallback(async () => {
    try { setData(await api.alerts()); } catch { /* */ }
  }, []);
  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, [load]);

  const fresh = data?.new_since_last ?? [];
  const repos = data?.by_repo ?? [];
  const tier = data?.cadence?.tier ?? 'baseline';

  return (
    <div className="panel col-6">
      <div className="panel-head">
        <div>
          <h3>Security Alerts</h3>
          <div className="sub">open dependabot alerts · sets grooming cadence</div>
        </div>
        <span className="chip">last check {ago(data?.last_run)}</span>
      </div>

      {data?.last_run == null ? (
        <div className="chip">No alert pass recorded yet.</div>
      ) : (
        <>
          <Tally totals={data.totals} />

          <div className="chip" style={{ marginBottom: 10 }}>
            <span style={{ color: tier === 'baseline' ? 'var(--good)' : SEV_COLOR[tier] ?? 'var(--warn)' }}>
              ● {cadenceLabel(data.cadence)}
            </span>
            {data.cadence?.reason ? ` — ${data.cadence.reason}` : ''}
          </div>

          {fresh.length > 0 && (
            <>
              <div className="chip" style={{ marginBottom: 4 }}>
                NEW since last check ({data.new_count})
              </div>
              {fresh.slice(0, 6).map(a => <NewRow key={`${a.repo}#${a.number}`} item={a} />)}
            </>
          )}

          {fresh.length === 0 && (
            <div className="chip" style={{ marginBottom: 4 }}>
              {data.first_run ? 'Baseline recorded — new alerts flagged from the next check.'
                              : 'No new alerts since the last check.'}
            </div>
          )}

          {repos.length > 0 && (
            <>
              <div className="chip" style={{ margin: '12px 0 4px' }}>By repo</div>
              {repos.slice(0, 5).map(r => <RepoRow key={r.repo} r={r} />)}
            </>
          )}

          <div className="chip" style={{ marginTop: 12 }}>
            {data.totals.open} open across {repos.length} repo(s)
            {data.alerts_disabled.length > 0 && ` · alerts disabled on ${data.alerts_disabled.length} repo(s)`}
          </div>

          {data.errors?.length > 0 && (
            <div className="err" style={{ marginTop: 8 }}>{data.errors[0]}</div>
          )}

          <ResolverControl />
        </>
      )}
    </div>
  );
}
