import { useState, type FormEvent } from "react";
import type { URLRequest } from "../types";

interface Props {
  onCreate: (payload: URLRequest) => Promise<boolean>;
  error: string | null;
}

export default function ShortenerForm({ onCreate, error }: Props) {
  const [url, setUrl] = useState("");
  const [customCode, setCustomCode] = useState("");
  const [ttl, setTtl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    setSubmitting(true);
    const payload: URLRequest = { url: url.trim() };
    if (customCode.trim()) payload.custom_code = customCode.trim();
    if (ttl.trim()) payload.ttl_seconds = Number(ttl);
    const ok = await onCreate(payload);
    setSubmitting(false);
    if (ok) {
      setUrl("");
      setCustomCode("");
      setTtl("");
      setDone(true);
      setTimeout(() => setDone(false), 1500);
    }
  };

  return (
    <form className="card shortener" onSubmit={submit}>
      <label className="field field--grow">
        <span>Destination URL</span>
        <input
          type="url"
          placeholder="https://example.com/very/long/path"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          required
        />
      </label>

      <label className="field field--sm">
        <span>Custom code</span>
        <input
          type="text"
          placeholder="promo"
          value={customCode}
          onChange={(e) => setCustomCode(e.target.value)}
        />
      </label>

      <label className="field field--xs">
        <span>TTL (sec)</span>
        <input
          type="number"
          min={1}
          placeholder="—"
          value={ttl}
          onChange={(e) => setTtl(e.target.value)}
        />
      </label>

      <button className="btn btn--primary" type="submit" disabled={submitting}>
        {submitting ? "Shortening…" : done ? "Done ✓" : "Shorten"}
      </button>

      {error && <p className="shortener__error" role="alert">{error}</p>}
    </form>
  );
}
