"use client";

import { useEffect, useState, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { AlertCircle, Clock } from "lucide-react";
import { api, type SearchResult } from "@/lib/api";
import SearchBar, { type SearchMode } from "@/components/SearchBar";
import ImageGrid from "@/components/ImageGrid";

function SearchPageInner() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [timeMs, setTimeMs] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const q = searchParams.get("q") ?? "";
  const mode = (searchParams.get("mode") ?? "keyword") as SearchMode;

  const doSearch = useCallback(async (query: string, searchMode: SearchMode) => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.search(query, searchMode, 60);
      setResults(res.results);
      setTimeMs(res.time_ms);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Search failed — is the backend running?");
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (q) doSearch(q, mode);
    else { setResults([]); setTimeMs(null); }
  }, [q, mode, doSearch]);

  const handleSearch = (newQ: string, newMode: SearchMode) =>
    router.push(`/search?q=${encodeURIComponent(newQ)}&mode=${newMode}`);

  const snippets: Record<number, string> = {};
  for (const r of results) snippets[r.image_id] = r.snippet;

  return (
    <div className="page-content" style={{ maxWidth: 1200 }}>
      {/* Search bar */}
      <div style={{ marginBottom: 24, maxWidth: 640 }}>
        <SearchBar defaultQuery={q} defaultMode={mode} onSearch={handleSearch} autoFocus={!q} />
      </div>

      {/* Result meta */}
      {q && !loading && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            marginBottom: 20,
            fontSize: 13,
          }}
        >
          {error ? (
            <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--danger)" }}>
              <AlertCircle size={14} />
              <span>{error}</span>
            </div>
          ) : (
            <>
              <span style={{ color: "var(--text-muted)" }}>
                <strong style={{ color: "var(--text-primary)" }}>{results.length}</strong>
                {" "}results for{" "}
                <strong style={{ color: "var(--accent-hover)" }}>&ldquo;{q}&rdquo;</strong>
              </span>
              {timeMs !== null && (
                <span style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--text-faint)", fontSize: 12 }}>
                  <Clock size={11} />
                  {timeMs.toFixed(0)}ms
                </span>
              )}
            </>
          )}
        </div>
      )}

      {/* Grid */}
      <ImageGrid
        images={results}
        loading={loading}
        snippets={snippets}
        emptyMessage={q ? `No results for "${q}"` : "Start by searching above"}
        emptyHint={q ? "Try a shorter term, different spelling, or browse the library" : "Type a word, phrase, or topic"}
      />

      {/* Idle hint */}
      {!q && !loading && (
        <div
          style={{
            textAlign: "center",
            paddingTop: 80,
            color: "var(--text-faint)",
            fontSize: 13,
          }}
        >
          Search across {" "}
          <span style={{ color: "var(--text-muted)" }}>8,615 indexed screenshots</span>
          {" "} using OCR text
        </div>
      )}
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense>
      <SearchPageInner />
    </Suspense>
  );
}
