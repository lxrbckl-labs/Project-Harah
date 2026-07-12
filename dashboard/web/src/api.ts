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
