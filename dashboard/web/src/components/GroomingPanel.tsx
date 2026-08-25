// Repo grooming panel — what harah's dependabot upkeep did to the owned repos.
//
// Two different routines write the state this renders, and they see different
// things. `groom.sh` sees open dependabot *pull requests* and reports what it
// merged or left for review — usually nothing, because the resolver gets there
// first. The `resolver` session does the real remediation, and POLICY's
// reporting rule ("every fix lands in the UI") makes its record — merges,
// resolutions, publishes, tooling repairs — this panel's job too. Rendering
// only groom.sh's half is why this panel could read "All repos current" while
// 169 resolver-closed alerts sat in the same file, unseen.
import { useEffect, useState, useCallback } from 'react';
import { api, type GroomingResp, type GroomingItem, type ResolverAction } from '../api';

function ago(ts?: number | null): string {
  if (!ts) return 'never';
  const s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function Row({ item, good }: { item: GroomingItem; good: boolean }) {
  return (
    <div className="arm-row" style={{ alignItems: 'center' }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          <a href={`https://github.com/${item.repo}/pull/${item.pr}`} target="_blank" rel="noreferrer"
             style={{ color: 'inherit', textDecoration: 'none' }}>
            {item.repo.split('/')[1]}#{item.pr}
          </a>
        </div>
        <div className="chip" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '100%' }}>
          {item.title}
          {good
            ? <span style={{ color: 'var(--good)' }}> · ✓ merged</span>
            : <span style={{ color: 'var(--warn, #d9a441)' }}> · {item.reason}</span>}
        </div>
      </div>
    </div>
  );
}

// Kinds the resolver writes. Anything unrecognised still renders — the label is
// just the raw kind — so a new kind never silently disappears from the record.
const KIND_COLOR: Record<string, string> = {
  resolved: 'var(--good)',
  resolution: 'var(--good)',
  deps: 'var(--good)',
  publish: 'var(--good)',
  tooling: 'var(--faint)',
  'tooling-repair': 'var(--faint)',
  housekeeping: 'var(--faint)',
  coverage: 'var(--faint)',
};

/** Did this reach the running container, and if not, how far behind is it?
 *
 *  A merge does not deploy on this host — only a `publish` commit builds an
 *  image — so "merged, not deployed" is the honest and usual answer, and the
 *  days-behind number is the KPI POLICY asks to be reported rather than filed.
 *  Older actions carry it as a number, newer ones as prose; read both. */
function deployStatus(a: ResolverAction): { text: string; color: string } {
  if (a.deployed === true) return { text: 'deployed', color: 'var(--good)' };

  let days = typeof a.days_behind_main === 'number' ? a.days_behind_main : null;
  if (days == null && a.deployed_or_days_behind) {
    const m = a.deployed_or_days_behind.match(/(\d+)\s*DAYS?\s*BEHIND/i);
    if (m) days = Number(m[1]);
  }
  if (days != null && days > 0) {
    return { text: `merged · ${days}d behind main`, color: 'var(--warn, #d9a441)' };
  }
  return { text: 'merged, not deployed', color: 'var(--faint)' };
}

function ActionRow({ a }: { a: ResolverAction }) {
  const repo = a.repo.includes('/') ? a.repo.split('/')[1] : a.repo;
  const closed = a.alerts_closed_count ?? a.alerts_closed?.length ?? 0;
  const detail = a.what || a.lineage || '';
  const dep = deployStatus(a);
  // Everything measured about this action, on hover — the verification output is
  // the part that makes a merge reviewable, and it is far too long to render.
  const title = [
    detail && `WHAT: ${detail}`,
    a.lineage && a.what && `LINEAGE: ${a.lineage}`,
    a.verified_by && `VERIFIED BY: ${a.verified_by}`,
    a.deploy_note || a.deployed_or_days_behind,
    a.alerts_closed?.length ? `ALERTS CLOSED: #${a.alerts_closed.join(', #')}` : '',
  ].filter(Boolean).join('\n\n');

  return (
    <div className="arm-row" style={{ alignItems: 'center' }} title={title || undefined}>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {a.pr != null
            ? <a href={`https://github.com/${a.repo}/pull/${a.pr}`} target="_blank" rel="noreferrer"
                 style={{ color: 'inherit', textDecoration: 'none' }}>{repo}#{a.pr}</a>
            : <span>{repo}</span>}
          <span style={{ color: KIND_COLOR[a.kind] ?? 'var(--faint)', marginLeft: 8, fontSize: 11, textTransform: 'uppercase', letterSpacing: '.06em' }}>
            {a.kind}
          </span>
          {closed > 0 && (
            <span style={{ color: 'var(--good)', marginLeft: 8, fontSize: 11 }}>
              {closed} alert{closed === 1 ? '' : 's'}
            </span>
          )}
        </div>
        <div className="chip" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '100%' }}>
          {detail || 'no description recorded'}
        </div>
        <div className="chip">
          <span style={{ color: dep.color }}>{dep.text}</span>
          <span> · {ago(a.timestamp)}</span>
        </div>
      </div>
    </div>
  );
}

export default function GroomingPanel() {
  const [data, setData] = useState<GroomingResp | null>(null);
  const load = useCallback(async () => {
    try { setData(await api.grooming()); } catch { /* */ }
  }, []);
  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [load]);

  const merged = data?.merged ?? [];
  const queued = data?.queued ?? [];
  // Newest first: the record is read to answer "what just happened", not to
  // read a history from the beginning. Copy before sorting — never sort state.
  const actions = [...(data?.resolver_actions ?? [])]
    .sort((x, y) => (y.timestamp ?? 0) - (x.timestamp ?? 0));
  const closedTotal = data?.totals?.alerts_closed_by_resolver
    ?? actions.reduce((n, a) => n + (a.alerts_closed_count ?? a.alerts_closed?.length ?? 0), 0);

  return (
    <div className="panel col-6">
      <div className="panel-head">
        <div>
          <h3>Repo Grooming</h3>
          <div className="sub">dependabot upkeep across owned repos (harah)</div>
        </div>
        <span className="chip">
          last pass {ago(data?.last_run)}{data?.dry_run ? ' · dry run' : ''}
        </span>
      </div>
      <div>
        {merged.map(m => <Row key={`${m.repo}#${m.pr}`} item={m} good />)}
        {queued.map(q => <Row key={`${q.repo}#${q.pr}`} item={q} good={false} />)}
        {merged.length === 0 && queued.length === 0 && (
          <div className="chip">
            {data?.last_run
              ? 'No open dependabot PRs — nothing for the grooming pass to merge or review.'
              : 'No grooming pass recorded yet.'}
          </div>
        )}
      </div>

      {actions.length > 0 && (
        <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid rgba(255,255,255,0.07)' }}>
          <div className="chip" style={{ marginBottom: 6 }}>
            Resolved by Harah — {actions.length} action{actions.length === 1 ? '' : 's'}
            {closedTotal > 0 && <span style={{ color: 'var(--good)' }}> · {closedTotal} alerts closed</span>}
            {data?.updated_by_resolver != null && <span> · last {ago(data.updated_by_resolver)}</span>}
          </div>
          {/* Scrolls rather than truncates: a record that hides its tail is the
              same failure as not rendering it at all. */}
          <div style={{ maxHeight: 340, overflowY: 'auto' }}>
            {actions.map((a, i) => <ActionRow key={`${a.repo}#${a.pr ?? 'x'}-${a.timestamp ?? i}`} a={a} />)}
          </div>
        </div>
      )}

      {data?.last_run != null && (
        <div className="chip" style={{ marginTop: 12 }}>
          {data.totals.merged} merged by grooming · {data.totals.queued} left for review · {data.totals.repos_with_prs} repo(s) with open dependabot PRs
        </div>
      )}
    </div>
  );
}
