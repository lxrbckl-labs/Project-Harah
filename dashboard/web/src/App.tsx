import { useEffect, useState, useCallback } from 'react';
import Aurora from './components/Aurora';
import Gauge from './components/Gauge';
import TrafficChart from './components/TrafficChart';
import ResourceChart from './components/ResourceChart';
import HardwareView from './components/HardwareView';
import {
  api, fmtBytes, fmtUptime,
  type Container, type StatsResp, type TrafficResp, type ResHistoryResp, type GuardianResp,
} from './api';

const SERVER_NAME = 'Homelab Server';
const SERVER_HOST = '192.168.68.200';

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 18) return 'Good afternoon';
  return 'Good evening';
}

// Traffic time-range tiers → window (minutes) + bucket granularity (seconds).
const TIERS = [
  { label: '15m', minutes: 15, bucket: 60 },
  { label: '1h', minutes: 60, bucket: 60 },
  { label: '3h', minutes: 180, bucket: 60 },
  { label: '24h', minutes: 1440, bucket: 300 },
  { label: '7d', minutes: 10080, bucket: 3600 },
  { label: '30d', minutes: 43200, bucket: 86400 },
];

const RES_TIERS = [
  { label: '6h', minutes: 360 },
  { label: '24h', minutes: 1440 },
  { label: '48h', minutes: 2880 },
];

export default function App() {
  const [containers, setContainers] = useState<Container[]>([]);
  const [stats, setStats] = useState<StatsResp | null>(null);
  const [traffic, setTraffic] = useState<TrafficResp | null>(null);
  const [resHistory, setResHistory] = useState<ResHistoryResp | null>(null);
  const [guardian, setGuardian] = useState<GuardianResp | null>(null);
  const [pending, setPending] = useState<Record<string, boolean>>({});
  const [err, setErr] = useState<string>('');
  const [tierIdx, setTierIdx] = useState(3); // default 24h
  const [resIdx, setResIdx] = useState(1);   // default 24h
  const tier = TIERS[tierIdx];
  const resTier = RES_TIERS[resIdx];

  const loadContainers = useCallback(async () => {
    try { setContainers((await api.containers()).containers); }
    catch (e) { setErr(String(e)); }
  }, []);
  const loadStats = useCallback(async () => {
    try { setStats(await api.stats()); } catch { /* transient */ }
  }, []);
  const loadTraffic = useCallback(async (minutes: number, bucket: number) => {
    try { setTraffic(await api.traffic(minutes, bucket)); } catch { /* transient */ }
  }, []);
  const loadResHistory = useCallback(async (minutes: number) => {
    try { setResHistory(await api.resourceHistory(minutes)); } catch { /* transient */ }
  }, []);
  const loadGuardian = useCallback(async () => {
    try { setGuardian(await api.guardian()); } catch { /* transient */ }
  }, []);

  useEffect(() => { loadContainers(); loadStats(); loadGuardian(); }, [loadContainers, loadStats, loadGuardian]);
  useEffect(() => { loadTraffic(tier.minutes, tier.bucket); }, [tier, loadTraffic]);
  useEffect(() => { loadResHistory(resTier.minutes); }, [resTier, loadResHistory]);

  useEffect(() => {
    const a = setInterval(loadStats, 4000);
    const b = setInterval(loadContainers, 6000);
    const c = setInterval(() => loadTraffic(tier.minutes, tier.bucket), 15000);
    const d = setInterval(() => loadResHistory(resTier.minutes), 20000);
    const e = setInterval(loadGuardian, 10000);
    return () => { clearInterval(a); clearInterval(b); clearInterval(c); clearInterval(d); clearInterval(e); };
  }, [loadStats, loadContainers, loadTraffic, loadResHistory, loadGuardian, tier, resTier]);

  async function toggleGuardian(enabled: boolean) {
    try { await api.guardianToggle(enabled); } catch (e) { setErr(String(e)); }
    loadGuardian();
  }
  async function armContainer(container: string, armed: boolean) {
    try { await api.guardianArm(container, armed); } catch (e) { setErr(String(e)); }
    loadGuardian();
  }
  async function armAll(names: string[], armed: boolean) {
    try { await Promise.all(names.map(n => api.guardianArm(n, armed))); }
    catch (e) { setErr(String(e)); }
    loadGuardian();
  }

  async function act(name: string, action: 'start' | 'stop') {
    setPending(p => ({ ...p, [name]: true }));
    setErr('');
    try {
      await api.action(name, action);
      await loadContainers();
      loadStats();
    } catch (e) {
      setErr(`${action} ${name}: ${e}`);
    } finally {
      setPending(p => ({ ...p, [name]: false }));
    }
  }

  const running = containers.filter(c => c.state === 'running');
  const stopped = containers.filter(c => c.state !== 'running');
  const host = stats?.host;
  const memPct = host?.mem.percent ?? 0;
  const maxHost = Math.max(1, ...Object.values(traffic?.by_host ?? {}));
  // per-container live resource usage, keyed by name (running containers only)
  const statByName = new Map((stats?.containers ?? []).map(c => [c.name, c]));
  // auto-defense state, merged into the container table
  const gEnabled = guardian?.enabled ?? false;
  const armedSet = new Set(guardian?.armed ?? []);
  const threatByContainer = new Map(
    (guardian?.threats ?? []).filter(t => t.container).map(t => [t.container as string, t]));
  const allNames = containers.map(c => c.name);
  const allArmed = allNames.length > 0 && allNames.every(n => armedSet.has(n));

  return (
    <>
      <div className="bg-layer" />
      <div className="aurora-wrap">
        <Aurora colorStops={['#5227FF', '#22d3ee', '#8b5cff']} amplitude={1.1} blend={0.55} speed={0.6} />
      </div>

      <div className="app">
        <div className="main">
          {/* header */}
          <header className="hdr">
            <div className="brand">
              <div className="logo">S</div>
              <div>
                <div className="bname">ServerManager</div>
                <div className="bsub">{SERVER_HOST}</div>
              </div>
            </div>
            <div className="hdr-right">
              <div className="hchip"><span className="lbl">CPU</span><span className="v">{host ? `${host.cpu_percent.toFixed(0)}%` : '—'}</span></div>
              <div className="hchip"><span className="lbl">MEM</span><span className="v">{memPct.toFixed(0)}%</span></div>
              <div className="hchip"><span className="live-dot" />{running.length} up</div>
            </div>
          </header>

          {err && <div className="panel col-12 err" style={{ marginBottom: 14 }}>⚠ {err}</div>}

          <div className="grid">
            {/* hero */}
            <div className="panel hero col-5">
              <div className="greet">{greeting()},</div>
              <div className="host">{SERVER_NAME}</div>
              <div className="hero-stat">
                <span className="big">{host ? fmtBytes(host.mem.used) : '—'}</span>
                <span className="unit">/ {host ? fmtBytes(host.mem.total) : '—'} RAM</span>
              </div>
              <div className="gradient-bar">
                <div className="mask" style={{ width: `${100 - memPct}%` }} />
              </div>
              <div className="bar-legend">
                <span>Memory {memPct.toFixed(0)}% used</span>
                <span>{host ? fmtBytes(host.mem.total - host.mem.used) : '—'} free</span>
              </div>
              <div style={{ display: 'flex', gap: 22, marginTop: 20 }}>
                <div><div className="chip">LOAD AVG</div><div className="codes" style={{ marginTop: 4 }}>{host ? host.load_avg.map((v, i) => <span key={i} className="code">{v.toFixed(2)}</span>) : '—'}</div></div>
                <div><div className="chip">CPU CORES</div><div style={{ fontWeight: 700, fontSize: 18 }}>{host?.cpu_count ?? '—'}</div></div>
                <div><div className="chip">CONTAINERS</div><div style={{ fontWeight: 700, fontSize: 18 }}>{running.length}<small style={{ color: 'var(--faint)' }}> / {containers.length}</small></div></div>
              </div>
            </div>

            {/* resources */}
            <div className="panel col-4">
              <div className="panel-head"><div><h3>Resources</h3><div className="sub">Live host utilization</div></div></div>
              <div className="ring-wrap">
                <Gauge value={host?.cpu_percent ?? 0} label="CPU" />
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div>
                    <div className="chip">MEMORY</div>
                    <div style={{ fontWeight: 750, fontSize: 20 }}>{memPct.toFixed(0)}%</div>
                    <div className="mini-bar"><span style={{ width: `${memPct}%`, background: 'linear-gradient(90deg,var(--accent),var(--violet))' }} /></div>
                  </div>
                  <div>
                    <div className="chip">DISK</div>
                    <div style={{ fontWeight: 750, fontSize: 20 }}>{host?.disk.percent.toFixed(0) ?? '—'}%</div>
                    <div className="mini-bar"><span style={{ width: `${host?.disk.percent ?? 0}%`, background: 'linear-gradient(90deg,var(--good),var(--accent-2))' }} /></div>
                  </div>
                </div>
              </div>
            </div>

            {/* top consumers */}
            <div className="panel col-3">
              <div className="panel-head"><div><h3>Top Load</h3><div className="sub">By CPU</div></div></div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {(stats?.containers ?? []).slice(0, 5).map(c => (
                  <div key={c.name}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5 }}>
                      <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 140 }}>{c.name}</span>
                      <span style={{ color: 'var(--muted)' }}>{c.cpu_percent.toFixed(1)}%</span>
                    </div>
                    <div className="mini-bar" style={{ marginTop: 6 }}><span style={{ width: `${Math.min(100, c.cpu_percent)}%`, background: 'linear-gradient(90deg,var(--accent-2),var(--accent))' }} /></div>
                  </div>
                ))}
                {!stats && <div className="loading">loading…</div>}
              </div>
            </div>

            {/* resource usage over time */}
            <div className="panel col-8">
              <div className="panel-head">
                <div><h3>Resource Usage</h3><div className="sub">Host CPU · memory · disk over time</div></div>
                <div className="seg">
                  {RES_TIERS.map((t, i) => (
                    <button key={t.label} className={resIdx === i ? 'on' : ''} onClick={() => setResIdx(i)}>{t.label}</button>
                  ))}
                </div>
              </div>
              <ResourceChart data={resHistory?.series ?? []} />
            </div>

            {/* hardware (Mac mini) — folded into the dashboard as one card */}
            <HardwareView host={host} />

            {/* traffic */}
            <div className="panel col-8">
              <div className="panel-head">
                <div><h3>Caddy Traffic</h3><div className="sub">Requests through the reverse proxy</div></div>
                <div className="seg">
                  {TIERS.map((t, i) => (
                    <button key={t.label} className={tierIdx === i ? 'on' : ''} onClick={() => setTierIdx(i)}>{t.label}</button>
                  ))}
                </div>
              </div>
              <div className="traffic-stats">
                <div className="s"><div className="n">{traffic?.requests ?? 0}</div><div className="l">requests</div></div>
                <div className="s"><div className="n">{traffic?.requests_per_min?.toFixed(1) ?? '0'}</div><div className="l">req / min</div></div>
                <div className="s"><div className="n">{fmtBytes(traffic?.bytes_out ?? 0)}</div><div className="l">served</div></div>
                <div className="s"><div className="n" style={{ color: (traffic?.rate_limited_429 ?? 0) > 0 ? 'var(--bad)' : undefined }}>{traffic?.rate_limited_429 ?? 0}</div><div className="l">rate-limited (429)</div></div>
              </div>
              <TrafficChart data={traffic?.series ?? []} bucketSeconds={traffic?.bucket_seconds ?? tier.bucket} />
              <div className="host-list">
                {Object.entries(traffic?.by_host ?? {}).slice(0, 5).map(([h, n]) => (
                  <div className="host-row" key={h}>
                    <span className="h">{h}</span>
                    <span className="track"><span style={{ width: `${(n / maxHost) * 100}%` }} /></span>
                    <span className="c">{n}</span>
                  </div>
                ))}
                {traffic && !traffic.available && <div className="chip">Caddy access log not available.</div>}
              </div>
            </div>

            {/* status + ips */}
            <div className="panel col-4">
              <div className="panel-head"><div><h3>Request Mix</h3><div className="sub">Last {tier.label}</div></div></div>
              <div style={{ display: 'flex', gap: 10, marginBottom: 18, flexWrap: 'wrap' }}>
                {Object.entries(traffic?.status_class ?? {}).map(([k, v]) => {
                  const col = k.startsWith('2') ? 'var(--good)' : k.startsWith('3') ? 'var(--accent-2)' : k.startsWith('4') ? 'var(--warn)' : 'var(--bad)';
                  return <div key={k} className="tile" style={{ padding: '10px 14px', flex: '1 0 60px' }}>
                    <div style={{ fontSize: 20, fontWeight: 750, color: col }}>{v}</div>
                    <div className="chip">{k}</div>
                  </div>;
                })}
              </div>
              <div className="chip" style={{ marginBottom: 8 }}>TOP CLIENT IPS</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
                {(traffic?.top_ips ?? []).map(t => (
                  <div key={t.ip} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                    <span style={{ fontVariantNumeric: 'tabular-nums' }}>{t.ip}</span>
                    <span style={{ color: 'var(--muted)' }}>{t.count}</span>
                  </div>
                ))}
                {(traffic?.top_ips?.length ?? 0) === 0 && <div className="chip">—</div>}
              </div>
            </div>

            {/* container management + auto-defense */}
            <div className="panel col-12">
              <div className="panel-head">
                <div>
                  <h3>Container Management</h3>
                  <div className="sub">Uptime, resources &amp; auto‑defense · start / stop only — never removed</div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                  {(guardian?.threats?.length ?? 0) > 0 &&
                    <span className="chip" style={{ color: 'var(--bad)', fontWeight: 700 }}>⚠ {guardian?.threats.length} under attack</span>}
                  <span className="chip">{running.length} running · {stopped.length} stopped</span>
                  <span className="chip" style={{ cursor: 'pointer' }} onClick={() => armAll(allNames, !allArmed)}>
                    {allArmed ? 'disarm all' : 'arm all'}
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className="chip">AUTO‑DEFENSE</span>
                    <button className={`switch ${gEnabled ? 'on' : ''}`} onClick={() => toggleGuardian(!gEnabled)} aria-label="toggle auto-defense">
                      <span className="knob" />
                    </button>
                  </div>
                </div>
              </div>
              <div className="ctable">
                <div className="row head">
                  <div>Container</div><div>Status</div><div>Uptime</div><div>CPU</div><div>Memory</div><div>Ports</div><div style={{ textAlign: 'center' }}>Defense</div><div style={{ textAlign: 'right' }}>Control</div>
                </div>
                {containers.map(c => {
                  const isRun = c.state === 'running';
                  const busy = pending[c.name];
                  const days = c.uptime_seconds / 86400;
                  const upW = Math.min(100, (days / 14) * 100);
                  const st = statByName.get(c.name);
                  const threat = threatByContainer.get(c.name);
                  const armedOn = armedSet.has(c.name);
                  return (
                    <div className={`row ${threat ? 'under-attack' : ''}`} key={c.id}>
                      <div className="cname">
                        <div className="cicon">{isRun ? '▣' : '▢'}</div>
                        <div className="t">
                          <div className="n">{c.name}</div>
                          <div className="i">{c.image}</div>
                        </div>
                      </div>
                      <div>
                        <span className={`badge ${isRun ? 'running' : 'stopped'}`}>
                          <span className="dot" />{isRun ? 'running' : c.state}
                        </span>
                        {threat && <div className="chip" style={{ color: 'var(--bad)', marginTop: 4 }}>⚠ {threat.top_ip_count} req · {threat.top_ip}</div>}
                      </div>
                      <div>
                        <div className="uptime">{isRun ? fmtUptime(c.uptime_seconds) : <small>—</small>}</div>
                        {isRun && <div className="uptrack"><span style={{ width: `${upW}%` }} /></div>}
                      </div>
                      <div>
                        {st ? (
                          <>
                            <div className="uptime" style={{ fontSize: 13 }}>{st.cpu_percent.toFixed(1)}%</div>
                            <div className="uptrack"><span style={{ width: `${Math.min(100, st.cpu_percent)}%`, background: 'linear-gradient(90deg,var(--accent-2),var(--accent))' }} /></div>
                          </>
                        ) : <small style={{ color: 'var(--faint)' }}>—</small>}
                      </div>
                      <div>
                        {st ? (
                          <>
                            <div className="uptime" style={{ fontSize: 12.5 }}>{st.mem_usage.split(' / ')[0]}</div>
                            <div className="uptrack"><span style={{ width: `${Math.min(100, st.mem_percent)}%`, background: 'linear-gradient(90deg,var(--good),var(--accent-2))' }} /></div>
                          </>
                        ) : <small style={{ color: 'var(--faint)' }}>—</small>}
                      </div>
                      <div className="codes">{c.ports ? c.ports.split(', ').map((p, i) => <span key={i} className="code" style={{ fontSize: 11 }}>{p}</span>) : <span className="chip">—</span>}</div>
                      <div style={{ display: 'flex', justifyContent: 'center' }}>
                        <button className={`switch sm ${armedOn ? 'on' : ''}`} onClick={() => armContainer(c.name, !armedOn)} aria-label={`arm ${c.name}`}>
                          <span className="knob" />
                        </button>
                      </div>
                      <div className="actions">
                        {isRun ? (
                          <button className="btn stop" disabled={busy} onClick={() => act(c.name, 'stop')}>
                            {busy ? <span className="spin" /> : 'Stop'}
                          </button>
                        ) : (
                          <button className="btn start" disabled={busy} onClick={() => act(c.name, 'start')}>
                            {busy ? <span className="spin" /> : 'Start'}
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
                {containers.length === 0 && <div className="loading">Loading containers…</div>}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
