import type {
  AnalyticsResponse,
  URLRequest,
  URLResponse,
  URLStats,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((body as { detail?: string }).detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

export async function createShortUrl(payload: URLRequest): Promise<URLResponse> {
  const res = await fetch(`${BASE}/api/urls`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return jsonOrThrow<URLResponse>(res);
}

export async function fetchStats(code: string): Promise<URLStats> {
  const res = await fetch(`${BASE}/api/urls/${encodeURIComponent(code)}`);
  return jsonOrThrow<URLStats>(res);
}

export async function fetchAnalytics(code: string): Promise<AnalyticsResponse> {
  const res = await fetch(
    `${BASE}/api/urls/${encodeURIComponent(code)}/analytics`,
  );
  return jsonOrThrow<AnalyticsResponse>(res);
}
