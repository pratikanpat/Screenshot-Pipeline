"use client";

import { useEffect, useState, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { api, type SearchResult } from "@/lib/api";
import SearchBar from "@/components/SearchBar";
import ImageGrid from "@/components/ImageGrid";

type Mode = "keyword" | "semantic" | "hybrid";

function SearchPageInner() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [timeMs, setTimeMs] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const q = searchParams.get("q") ?? "";
  const mode = (searchParams.get("mode") ?? "keyword") as Mode;

  const doSearch = useCallback(async (query: string, searchMode: Mode) => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.search(query, searchMode, 40);
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

  const handleSearch = (newQ: string, newMode: Mode) => {
    router.push(`/search?q=${encodeURIComponent(newQ)}&mode=${newMode}`);
  };

  // Build snippet map for ImageGrid
  const snippets: Record<number, string> = {};
  for (const r of results) snippets[r.image_id] = r.snippet;

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 space-y-8">
      {/* Search bar */}
      <SearchBar defaultQuery={q} defaultMode={mode} onSearch={handleSearch} />

      {/* Result meta */}
      {q && !loading && (
        <div className="flex items-center gap-3 text-sm text-zinc-500">
          {error ? (
            <span className="text-red-400">⚠ {error}</span>
          ) : (
            <>
              <span>
                <strong className="text-zinc-300">{results.length}</strong> results
                for "<span className="text-indigo-400">{q}</span>"
              </span>
              {timeMs !== null && (
                <span className="text-zinc-700">· {timeMs.toFixed(0)}ms</span>
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
      />

      {/* Empty hint */}
      {!q && (
        <div className="text-center py-16 text-zinc-600">
          Type a keyword above to search your screenshots
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
