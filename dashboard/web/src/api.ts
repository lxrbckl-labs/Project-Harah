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
  health: 'healthy' | 'unhealthy' | 'starting' | 'none';
  restart_count: number;
  crash_looping: boolean;
  project: string;
}

export interface Geo { country: string; cc: string; city: string; }

export interface ContainerHistoryResp {
  name: string;
  series: { t: number; cpu: number; mem: number }[];
  count: number;
}

export interface BackupDb {
  name: string;
  image: string;
  state: string;
  user: string;
  db: string;
  last_backup: { file: string; ts: number; size: number } | null;
  status: { state: string; ts?: number; size?: number; file?: string; error?: string };
}

export interface BackupsResp { databases: BackupDb[]; backup_dir: string; }

export interface GroomingItem { kind: string; repo: string; pr: number; title: string; reason: string; }

export interface GroomingResp {
  last_run: number | null;
  dry_run: boolean;
  merged: GroomingItem[];
  queued: GroomingItem[];
  totals: { merged: number; queued: number; repos_with_prs: number };
}

export interface ResolverResp {
  cadence: string;
  label: string;
  choices: string[];
  last_start: string | null;
  last_end: string | null;
  running: boolean;
  ok?: boolean;
  message?: string;
}

export interface AlertItem {
  repo: string; number: number; severity: string;
  package: string; summary: string; url: string; created_at: string;
}

export interface AlertRepo {
  repo: string; open: number;
  critical: number; high: number; medium: number; low: number;
}

export interface AlertsResp {
  last_run: number | null;
  totals: { critical: number; high: number; medium: number; low: number; open: number };
  new_since_last: AlertItem[];
  new_count: number;
  by_repo: AlertRepo[];
  alerts_disabled: string[];
  errors: string[];
  first_run?: boolean;
  cadence: { tier: string; interval_seconds: number | null; reason: string };
}

export interface ContainersResp {
  containers: Container[];
  count: number;
}

export interface HostStats {
  cpu_percent: number;
  cpu_count: number;
  load_avg: number[];
  mem: { used: number; total: number; free: number; percent: number };
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
  docker_mem: { used: number; total: number; percent: number };
}

export interface StorageVol {
  mount: string;
  name: string;
  device: string;
  fstype: string;
  total: number;
  used: number;
  free: number;
  percent: number;
  external: boolean;
  containers: string[];
}

export interface StorageResp { volumes: StorageVol[]; }

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
  geo: Geo | null;
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
  banned_ips: string[];
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
  storage: () => j<StorageResp>('/api/storage'),
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
  guardianBan: (ip: string, banned: boolean) =>
    j<{ banned_ips: string[] }>('/api/guardian/ban', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ip, banned }),
    }),
  action: (name: string, action: 'start' | 'stop' | 'restart') =>
    j<{ name: string; action: string; state: string; ok: boolean }>(
      `/api/containers/${encodeURIComponent(name)}/${action}`,
      { method: 'POST' },
    ),
  logs: (name: string, tail = 300) =>
    j<{ name: string; tail: number; logs: string }>(
      `/api/containers/${encodeURIComponent(name)}/logs?tail=${tail}`),
  containerHistory: (name: string, minutes = 360) =>
    j<ContainerHistoryResp>(
      `/api/containers/${encodeURIComponent(name)}/history?minutes=${minutes}`),
  backups: () => j<BackupsResp>('/api/backups'),
  grooming: () => j<GroomingResp>('/api/grooming'),
  alerts: () => j<AlertsResp>('/api/alerts'),
  resolver: () => j<ResolverResp>('/api/resolver'),
  setResolverCadence: (choice: string) =>
    j<ResolverResp>(`/api/resolver/cadence/${encodeURIComponent(choice)}`, { method: 'POST' }),
  backupNow: (name: string) =>
    j<{ started: string }>(`/api/backups/${encodeURIComponent(name)}`, { method: 'POST' }),
  pins: () => j<{ pinned: string[] }>('/api/pins'),
  setPin: (name: string, pinned: boolean) =>
    j<{ pinned: string[] }>('/api/pins', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, pinned }),
    }),
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
