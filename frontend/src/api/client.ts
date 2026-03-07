// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
// Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
import axios from 'axios';

export const apiClient = axios.create({
  baseURL: '/api',
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
});

export function setAuthToken(token: string): void {
  apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`;
}

export function clearAuthToken(): void {
  delete apiClient.defaults.headers.common['Authorization'];
}

// ─── Response interceptor: unwrap envelope ────────────────────────────────────
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const message: string =
      error?.response?.data?.message ??
      error?.response?.data?.detail ??
      error.message ??
      'Unknown error';
    return Promise.reject(new Error(message));
  }
);

// ─── Typed API helpers ────────────────────────────────────────────────────────

export interface APIEnvelope<T> {
  status: string;
  data: T;
  meta: Record<string, unknown>;
}

export interface TokenData {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface DeviceData {
  id: number;
  hostname: string;
  ip_address: string;
  device_type: string;
  vendor: string;
  os_version: string | null;
  status: string;
  last_seen: string | null;
  neighbors: unknown;
}

export interface LicenseStatus {
  tier: string;
  is_active: boolean;
  expires_at: string | null;
  max_devices: number | null;
  days_remaining: number | null;
  in_grace_period: boolean;
  /** One of: "ok" | "warning" | "critical" | "grace" | "expired" */
  expiry_alert_level: string;
  message: string | null;
}

export interface PredictionData {
  device_id: number;
  failure_probability: number;
  time_to_failure_hours: number | null;
  alert_created: boolean;
  message: string;
}

export const authAPI = {
  login: (username: string, password: string) =>
    apiClient.post<APIEnvelope<TokenData>>('/auth/login', { username, password }),
  register: (username: string, email: string, password: string) =>
    apiClient.post('/auth/register', { username, email, password }),
  refresh: (token: string) =>
    apiClient.post('/auth/refresh', null, { params: { token } }),
};

export const devicesAPI = {
  list: () => apiClient.get<APIEnvelope<DeviceData[]>>('/devices'),
  get: (id: number) => apiClient.get<APIEnvelope<DeviceData>>(`/devices/${id}`),
  create: (payload: { hostname: string; ip_address: string; device_type?: string; vendor?: string }) =>
    apiClient.post<APIEnvelope<DeviceData>>('/devices', payload),
  delete: (id: number) => apiClient.delete(`/devices/${id}`),
};

export const topologyAPI = {
  map: () => apiClient.get('/topology/map'),
  discover: (payload: {
    seed_ip: string;
    username: string;
    password: string;
    device_type: string;
    secret?: string;
  }) => apiClient.post('/topology/discover', payload),
};

export const aiAPI = {
  predict: (deviceId: number, metrics: { cpu_percent: number; ram_percent: number; error_rate: number; latency_ms: number }) =>
    apiClient.get<APIEnvelope<PredictionData>>(`/ai/predict/${deviceId}`, { params: metrics }),
};

export const licenseAPI = {
  activate: (key: string) => apiClient.post('/license/activate', { key }),
  status: () => apiClient.get<APIEnvelope<LicenseStatus>>('/license/status'),
};
