// Typed client for the ServerManager backend API.

export interface Container {
  id: string;
  name: string;
  image: string;
  state: 'running' | 'exited' | 'created' | 'paused' | string;
  status: string;
  ports: string;
  uptime_seconds: number;
  started_at: number | null;
}

export interface ContainersResp {
  containers: Container[];
  count: number;
}

export interface HostStats {
  cpu_percent: number;
  cpu_count: number;
  load_avg: number[];
  mem: { used: number; total: number; percent: number };
  disk: { used: number; total: number; percent: number };
}

export interface ContainerStat {
  name: string;
  cpu_percent: number;
  mem_usage: string;
  mem_percent: number;
}

export interface StatsResp {
  host: HostStats;
  containers: ContainerStat[];
  container_count: number;
}

export interface TrafficResp {
  available: boolean;
  minutes: number;
  bucket_seconds: number;
  requests: number;
  requests_per_min: number;
  bytes_out: number;
  rate_limited_429: number;
  peak_per_bucket: number;
  by_host: Record<string, number>;
  status_class: Record<string, number>;
  top_ips: { ip: string; count: number }[];
  series: { t: number; count: number }[];
}

export interface ResSample {
  t: number;
  cpu: number;
  mem: number;
  disk: number;
  load1: number;
}

export interface ResHistoryResp {
  minutes: number;
  bucket_seconds?: number;
  series: ResSample[];
  count: number;
}

export interface Threat {
  host: string;
  container: string | null;
  top_ip: string;
  top_ip_count: number;
  auth_fails: number;
  total: number;
  window_sec: number;
  private: boolean;
  severity: string;
  ts: number;
}

export interface GuardianAction {
  container: string;
  host: string;
  top_ip: string;
  reason: string;
  ts: number;
}

export interface GuardianResp {
  enabled: boolean;
  armed: string[];
  window_sec: number;
  ip_req_threshold: number;
  auth_fail_threshold: number;
  cooldown_sec: number;
  ignore_private: boolean;
  allowlist: string[];
  threats: Threat[];
  actions: GuardianAction[];
  mapping: Record<string, string>;
}

async function j<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) {
    let detail = r.statusText;
    try {
      detail = (await r.json()).detail ?? detail;
    } catch { /* ignore */ }
    throw new Error(detail);
  }
  return r.json();
}

export const api = {
  containers: () => j<ContainersResp>('/api/containers'),
  stats: () => j<StatsResp>('/api/stats'),
  traffic: (minutes = 15, bucket = 0) =>
    j<TrafficResp>(`/api/traffic?minutes=${minutes}&bucket=${bucket}`),
  resourceHistory: (minutes = 1440) =>
    j<ResHistoryResp>(`/api/resources/history?minutes=${minutes}`),
  guardian: () => j<GuardianResp>('/api/guardian'),
  guardianToggle: (enabled: boolean) =>
    j<{ enabled: boolean }>('/api/guardian/toggle', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    }),
  guardianArm: (container: string, armed: boolean) =>
    j<{ armed: string[] }>('/api/guardian/arm', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ container, armed }),
    }),
  guardianConfig: (patch: Partial<Pick<GuardianResp, 'ignore_private' | 'allowlist' | 'ip_req_threshold' | 'auth_fail_threshold'>>) =>
    j<Record<string, unknown>>('/api/guardian/config', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    }),
  action: (name: string, action: 'start' | 'stop' | 'restart') =>
    j<{ name: string; action: string; state: string; ok: boolean }>(
      `/api/containers/${encodeURIComponent(name)}/${action}`,
      { method: 'POST' },
    ),
};

// ---- formatters ----

export function fmtBytes(n: number): string {
  if (!n) return '0 B';
  const u = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < u.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(v < 10 && i > 0 ? 1 : 0)} ${u[i]}`;
}

export function fmtUptime(sec: number): string {
  if (!sec) return '—';
  const d = Math.floor(sec / 86400);
  const h = Math.floor((sec % 86400) / 3600);
  const m = Math.floor((sec % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m`;
  return `${sec}s`;
}
