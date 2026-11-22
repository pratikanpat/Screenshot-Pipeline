"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";

type Mode = "keyword" | "semantic" | "hybrid";

interface Props {
  defaultQuery?: string;
  defaultMode?: Mode;
  autoFocus?: boolean;
  onSearch?: (q: string, mode: Mode) => void;
}

export default function SearchBar({
  defaultQuery = "",
  defaultMode = "keyword",
  autoFocus = false,
  onSearch,
}: Props) {
  const router = useRouter();
  const [q, setQ] = useState(defaultQuery);
  const [mode, setMode] = useState<Mode>(defaultMode);
  const [, startTransition] = useTransition();
  const inputRef = useRef<HTMLInputElement>(null);

  // Cmd/Ctrl+K global shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const submit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!q.trim()) return;
    if (onSearch) {
      onSearch(q.trim(), mode);
    } else {
      startTransition(() => {
        router.push(`/search?q=${encodeURIComponent(q.trim())}&mode=${mode}`);
      });
    }
  };

  const modes: { value: Mode; label: string; desc: string }[] = [
    { value: "keyword", label: "Keyword", desc: "Exact & prefix match" },
    { value: "semantic", label: "Semantic", desc: "Search by meaning (CLIP)" },
    { value: "hybrid", label: "Hybrid", desc: "Best of both" },
  ];

  return (
    <div className="w-full max-w-2xl mx-auto space-y-3">
      {/* Search input */}
      <form onSubmit={submit} className="relative">
        <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none">
          <svg className="w-5 h-5 text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M21 21l-4.35-4.35M11 19A8 8 0 1 0 11 3a8 8 0 0 0 0 16z" />
          </svg>
        </div>
        <input
          ref={inputRef}
          autoFocus={autoFocus}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder='Search screenshots… (⌘K)'
          className="w-full pl-12 pr-24 py-4 rounded-2xl bg-zinc-900 border border-zinc-700 text-zinc-100 placeholder-zinc-500 text-base focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
        />
        {q && (
          <button
            type="button"
            onClick={() => setQ("")}
            className="absolute right-16 inset-y-0 flex items-center text-zinc-500 hover:text-zinc-300 px-2"
          >
            ✕
          </button>
        )}
        <button
          type="submit"
          className="absolute right-3 top-1/2 -translate-y-1/2 bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-xl text-sm font-medium transition"
        >
          Search
        </button>
      </form>

      {/* Mode selector */}
      <div className="flex items-center gap-2">
        {modes.map((m) => (
          <button
            key={m.value}
            onClick={() => setMode(m.value)}
            title={m.desc}
            className={`px-3 py-1 rounded-lg text-xs font-medium border transition ${
              mode === m.value
                ? "bg-indigo-600 border-indigo-600 text-white"
                : "border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200"
            }`}
          >
            {m.label}
          </button>
        ))}
        <span className="text-xs text-zinc-600 ml-1">
          {modes.find((m) => m.value === mode)?.desc}
        </span>
      </div>
    </div>
  );
}
