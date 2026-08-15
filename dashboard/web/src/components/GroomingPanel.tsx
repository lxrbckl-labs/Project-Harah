// Repo grooming panel — what the harah dependabot routine merged and queued.
import { useEffect, useState, useCallback } from 'react';
import { api, type GroomingResp, type GroomingItem } from '../api';

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
            {data?.last_run ? 'All repos current — nothing to merge or review.' : 'No grooming pass recorded yet.'}
          </div>
        )}
      </div>
      {data?.last_run != null && (
        <div className="chip" style={{ marginTop: 12 }}>
          {data.totals.merged} merged · {data.totals.queued} queued for Alex · {data.totals.repos_with_prs} repo(s) with open dependabot PRs
        </div>
      )}
    </div>
  );
}
