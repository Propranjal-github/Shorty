import { useState } from "react";
import type { URLResponse } from "../types";

interface CreatedLink extends URLResponse {
  clicks: number;
}

interface Props {
  links: CreatedLink[];
  activeCode: string | null;
  onOpenAnalytics: (code: string) => void;
  onRefresh: (code: string) => void;
  onRemove: (code: string) => void;
}

export default function LinkList({
  links,
  activeCode,
  onOpenAnalytics,
  onRefresh,
  onRemove,
}: Props) {
  return (
    <ul className="links">
      {links.map((link) => (
        <LinkRow
          key={link.short_code}
          link={link}
          active={activeCode === link.short_code}
          onOpenAnalytics={onOpenAnalytics}
          onRefresh={onRefresh}
          onRemove={onRemove}
        />
      ))}
    </ul>
  );
}

interface RowProps {
  link: CreatedLink;
  active: boolean;
  onOpenAnalytics: (code: string) => void;
  onRefresh: (code: string) => void;
  onRemove: (code: string) => void;
}

function LinkRow({ link, active, onOpenAnalytics, onRefresh, onRemove }: RowProps) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link.short_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked; ignore */
    }
  };

  return (
    <li className={`link ${active ? "link--active" : ""}`}>
      <div className="link__main">
        <a className="link__short" href={link.short_url} target="_blank" rel="noreferrer">
          {link.short_url}
        </a>
        <span className="link__dest" title={link.original_url}>
          → {link.original_url}
        </span>
      </div>
      <div className="link__meta">
        <span className="pill">{link.clicks} clicks</span>
        {link.expires_at && <span className="pill pill--muted">expires</span>}
      </div>
      <div className="link__actions">
        <button className="btn btn--ghost" onClick={copy}>
          {copied ? "Copied ✓" : "Copy"}
        </button>
        <button className="btn btn--ghost" onClick={() => onRefresh(link.short_code)}>
          Refresh
        </button>
        <button
          className={`btn ${active ? "btn--primary" : "btn--ghost"}`}
          onClick={() => onOpenAnalytics(link.short_code)}
        >
          Analytics
        </button>
        <button className="btn btn--danger-ghost" onClick={() => onRemove(link.short_code)}>
          ✕
        </button>
      </div>
    </li>
  );
}
