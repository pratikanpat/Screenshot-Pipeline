"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";
import { Search, X } from "lucide-react";

export type SearchMode = "keyword" | "semantic" | "hybrid";

interface Props {
  defaultQuery?: string;
  defaultMode?: SearchMode;
  autoFocus?: boolean;
  onSearch?: (q: string, mode: SearchMode) => void;
  compact?: boolean;
}

const MODES: { value: SearchMode; label: string; desc: string; available: boolean }[] = [
  { value: "keyword",  label: "Keyword",  desc: "Exact & prefix match",   available: true },
  { value: "semantic", label: "Semantic", desc: "By meaning — coming soon", available: false },
  { value: "hybrid",   label: "Hybrid",   desc: "Best of both — coming soon", available: false },
];

export default function SearchBar({
  defaultQuery = "",
  defaultMode = "keyword",
  autoFocus = false,
  onSearch,
  compact = false,
}: Props) {
  const router = useRouter();
  const [q, setQ] = useState(defaultQuery);
  const [mode, setMode] = useState<SearchMode>(defaultMode);
  const [, startTransition] = useTransition();
  const inputRef = useRef<HTMLInputElement>(null);

  /* sync when URL changes */
  useEffect(() => { setQ(defaultQuery); }, [defaultQuery]);
  useEffect(() => { setMode(defaultMode); }, [defaultMode]);

  /* ⌘K / Ctrl+K global shortcut */
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const submit = (e?: React.FormEvent) => {
    e?.preventDefault();
    const trimmed = q.trim();
    if (!trimmed) return;
    if (onSearch) {
      onSearch(trimmed, mode);
    } else {
      startTransition(() => {
        router.push(`/search?q=${encodeURIComponent(trimmed)}&mode=${mode}`);
      });
    }
  };

  return (
    <div style={{ width: "100%", maxWidth: compact ? "none" : 640 }}>
      {/* Input row */}
      <form onSubmit={submit} style={{ position: "relative" }}>
        {/* Search icon */}
        <div
          style={{
            position: "absolute",
            left: 14,
            top: 0,
            bottom: 0,
            display: "flex",
            alignItems: "center",
            pointerEvents: "none",
          }}
        >
          <Search size={16} color="var(--text-faint)" />
        </div>

        <input
          ref={inputRef}
          autoFocus={autoFocus}
          value={q}
          onChange={e => setQ(e.target.value)}
          onKeyDown={e => e.key === "Enter" && submit()}
          placeholder="Search screenshots…"
          className="search-input"
        />

        {/* Clear */}
        {q && (
          <button
            type="button"
            onClick={() => setQ("")}
            style={{
              position: "absolute",
              right: compact ? 12 : 90,
              top: 0,
              bottom: 0,
              display: "flex",
              alignItems: "center",
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "var(--text-faint)",
              padding: "0 4px",
            }}
          >
            <X size={14} />
          </button>
        )}

        {/* Keyboard hint OR submit button */}
        {compact ? (
          <div
            style={{
              position: "absolute",
              right: 12,
              top: 0,
              bottom: 0,
              display: "flex",
              alignItems: "center",
              gap: 4,
              pointerEvents: "none",
            }}
          >
            {!q && (
              <kbd
                style={{
                  fontSize: 11,
                  color: "var(--text-faint)",
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border)",
                  borderRadius: 4,
                  padding: "2px 5px",
                  fontFamily: "monospace",
                }}
              >
                ⌘K
              </kbd>
            )}
          </div>
        ) : (
          <button
            type="submit"
            className="btn btn-primary"
            style={{ position: "absolute", right: 6, top: 6, bottom: 6 }}
          >
            Search
          </button>
        )}
      </form>

      {/* Mode pills (only show in full mode) */}
      {!compact && (
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 10 }}>
          {MODES.map(m => (
            <button
              key={m.value}
              onClick={() => m.available && setMode(m.value)}
              title={m.desc}
              className={`chip ${mode === m.value && m.available ? "active" : ""}`}
              style={{
                opacity: m.available ? 1 : 0.4,
                cursor: m.available ? "pointer" : "not-allowed",
              }}
            >
              {m.label}
              {!m.available && (
                <span style={{ fontSize: 10, color: "var(--text-faint)" }}>·soon</span>
              )}
            </button>
          ))}
          <span style={{ fontSize: 12, color: "var(--text-faint)", marginLeft: 2 }}>
            {MODES.find(m => m.value === mode)?.desc}
          </span>
        </div>
      )}
    </div>
  );
}
