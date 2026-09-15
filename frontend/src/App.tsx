import { useCallback, useEffect, useState } from "react";
import { createShortUrl, fetchAnalytics, fetchStats } from "./api";
import type { AnalyticsResponse, URLRequest, URLResponse } from "./types";
import ShortenerForm from "./components/ShortenerForm";
import LinkList from "./components/LinkList";
import AnalyticsPanel from "./components/AnalyticsPanel";
import "./App.css";

interface CreatedLink extends URLResponse {
  clicks: number;
}

const STORAGE_KEY = "shorty:links";

function loadLinks(): CreatedLink[] {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved ? (JSON.parse(saved) as CreatedLink[]) : [];
  } catch {
    return [];
  }
}

export default function App() {
  const [links, setLinks] = useState<CreatedLink[]>(loadLinks);
  const [error, setError] = useState<string | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);
  const [analyticsCode, setAnalyticsCode] = useState<string | null>(null);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(links.slice(0, 50)));
  }, [links]);

  const persist = useCallback((updater: (prev: CreatedLink[]) => CreatedLink[]) => {
    setLinks((prev) => updater(prev));
  }, []);

  const handleCreated = useCallback(
    async (payload: URLRequest) => {
      setError(null);
      try {
        const created = await createShortUrl(payload);
        persist((prev) => [{ ...created, clicks: 0 }, ...prev].slice(0, 50));
        return true;
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to shorten URL");
        return false;
      }
    },
    [persist],
  );

  const handleRefresh = useCallback(
    async (code: string) => {
      try {
        const stats = await fetchStats(code);
        persist((prev) =>
          prev.map((l) =>
            l.short_code === code ? { ...l, clicks: stats.click_count } : l,
          ),
        );
      } catch {
        /* keep stale; the link may have been deleted */
      }
    },
    [persist],
  );

  const handleRemove = useCallback(
    (code: string) => {
      persist((prev) => prev.filter((l) => l.short_code !== code));
      if (analyticsCode === code) {
        setAnalytics(null);
        setAnalyticsCode(null);
      }
    },
    [persist, analyticsCode],
  );

  const handleOpenAnalytics = useCallback(async (code: string) => {
    setAnalyticsCode(code);
    setAnalytics(null);
    setLoadingAnalytics(true);
    try {
      setAnalytics(await fetchAnalytics(code));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load analytics");
    } finally {
      setLoadingAnalytics(false);
    }
  }, []);

  return (
    <div className="app">
      <header className="app__header">
        <div className="app__brand">
          <span className="app__logo">S</span>
          <div>
            <h1>Shorty</h1>
            <p>A distributed URL shortener.</p>
          </div>
        </div>
        <a className="app__docs" href="/docs" target="_blank" rel="noreferrer">
          API docs ↗
        </a>
      </header>

      <main className="app__main">
        <ShortenerForm onCreate={handleCreated} error={error} />

        <section className="panel">
          <div className="panel__head">
            <h2>Your shortened links</h2>
            <span className="panel__hint">{links.length} stored</span>
          </div>
          {links.length === 0 ? (
            <p className="panel__empty">No links yet — shorten one above.</p>
          ) : (
            <LinkList
              links={links}
              activeCode={analyticsCode}
              onOpenAnalytics={handleOpenAnalytics}
              onRefresh={handleRefresh}
              onRemove={handleRemove}
            />
          )}
        </section>

        <AnalyticsPanel
          data={analytics}
          code={analyticsCode}
          loading={loadingAnalytics}
        />
      </main>

      <footer className="app__footer">
        <span>
          FastAPI · snowflake IDs · LRU cache · token-bucket limiter · background
          analytics
        </span>
      </footer>
    </div>
  );
}
