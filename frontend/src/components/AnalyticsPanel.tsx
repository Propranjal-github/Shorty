import type { AnalyticsResponse } from "../types";

interface Props {
  data: AnalyticsResponse | null;
  code: string | null;
  loading: boolean;
}

export default function AnalyticsPanel({ data, code, loading }: Props) {
  if (!code) return null;

  return (
    <section className="panel analytics">
      <div className="panel__head">
        <h2>Analytics</h2>
        <span className="panel__hint">/{code}</span>
      </div>

      {loading ? (
        <p className="panel__empty">Loading…</p>
      ) : data ? (
        <div className="analytics__body">
          <div className="analytics__totals">
            <div className="stat">
              <span className="stat__value">{data.total_clicks}</span>
              <span className="stat__label">total clicks</span>
            </div>
            <div className="stat">
              <span className="stat__value">{data.recent.length}</span>
              <span className="stat__label">active hours</span>
            </div>
            <div className="stat">
              <span className="stat__value">{data.top_referrers.length}</span>
              <span className="stat__label">referrers</span>
            </div>
          </div>

          <div className="chart">
            <h3>Clicks per hour (last 24h)</h3>
            {data.recent.length === 0 ? (
              <p className="panel__empty">No clicks in this window yet.</p>
            ) : (
              <Bars
                values={data.recent.map((b) => b.clicks)}
                labels={data.recent.map((b) => fmtHour(b.bucket))}
              />
            )}
          </div>

          <div className="chart">
            <h3>Top referrers</h3>
            {data.top_referrers.length === 0 ? (
              <p className="panel__empty">No referrer data yet.</p>
            ) : (
              <HBars
                values={data.top_referrers.map((r) => r.count)}
                labels={data.top_referrers.map((r) => r.referrer ?? "direct")}
              />
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}

interface BarsProps {
  values: number[];
  labels: string[];
}

function Bars({ values, labels }: BarsProps) {
  const max = Math.max(1, ...values);
  return (
    <div className="bars">
      {values.map((v, i) => (
        <div className="bars__col" key={`${labels[i]}-${i}`}>
          <div className="bars__bar" style={{ height: `${(v / max) * 100}%` }} />
          <span className="bars__label">{labels[i]}</span>
        </div>
      ))}
    </div>
  );
}

function HBars({ values, labels }: BarsProps) {
  const max = Math.max(1, ...values);
  return (
    <ul className="hbars">
      {labels.map((label, i) => (
        <li className="hbars__row" key={`${label}-${i}`}>
          <span className="hbars__label" title={label}>
            {label}
          </span>
          <div className="hbars__track">
            <div
              className="hbars__fill"
              style={{ width: `${(values[i] / max) * 100}%` }}
            />
          </div>
          <span className="hbars__count">{values[i]}</span>
        </li>
      ))}
    </ul>
  );
}

function fmtHour(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
