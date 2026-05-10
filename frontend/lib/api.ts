const BASE = process.env.NEXT_PUBLIC_API_URL || "";

export type Flight = {
  id: number;
  source: string;
  airline: string;
  flight_number: string;
  origin: string;
  destination: string;
  departure_at: string;
  arrival_at: string;
  duration_minutes: number;
  stops: number;
  price_twd: number;
  currency: string;
  baggage_included: boolean;
  fare_class: string;
  deep_link: string;
  fetched_at: string;
};

export type CalendarCell = {
  date: string;
  min_price_twd: number;
  flight_count: number;
};

export type TrendPoint = {
  recorded_at: string;
  min_price_twd: number;
};

export type Alert = {
  id: number;
  origin: string;
  destination: string;
  airline: string;
  flight_number: string;
  departure_at: string;
  price_twd: number;
  sent_at: string;
  delivered: boolean;
  message: string;
};

export type Settings = {
  airlines: string[];
  routes: { origin: string; destination: string; max_price: number }[];
  filters: Record<string, unknown>;
  search: Record<string, unknown>;
  notification: Record<string, unknown>;
};

export const fetcher = async <T,>(path: string): Promise<T> => {
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) throw new Error(`API ${path} → ${r.status}`);
  return r.json() as Promise<T>;
};

export const apiUrls = {
  cheapest: (limit = 10) => `/api/flights/cheapest?limit=${limit}`,
  flights: (params: Record<string, string | number | undefined>) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "") q.set(k, String(v));
    });
    const s = q.toString();
    return `/api/flights${s ? `?${s}` : ""}`;
  },
  calendar: (origin: string, destination: string, days = 90) =>
    `/api/calendar?origin=${origin}&destination=${destination}&days=${days}`,
  trends: (origin: string, destination: string, airline?: string) =>
    `/api/trends?origin=${origin}&destination=${destination}${airline ? `&airline=${airline}` : ""}`,
  settings: () => `/api/settings`,
  alerts: (limit = 100) => `/api/alerts?limit=${limit}`,
  scan: (notify = false) => `/api/flights/scan?notify=${notify}`,
  testNotify: () => `/api/notifier/test`,
};

export async function triggerScan(notify = false): Promise<unknown> {
  const r = await fetch(`${BASE}${apiUrls.scan(notify)}`, { method: "POST" });
  if (!r.ok) throw new Error(`scan failed ${r.status}`);
  return r.json();
}

export type TestNotifyResult = {
  telegram_configured: boolean;
  discord_configured: boolean;
  telegram_sent: boolean;
  discord_sent: boolean;
  error?: string;
};

export async function sendTestNotification(): Promise<TestNotifyResult> {
  const r = await fetch(`${BASE}${apiUrls.testNotify()}`, { method: "POST" });
  if (!r.ok) throw new Error(`test failed ${r.status}`);
  return r.json();
}
