"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type ProcessStatus, type CategoryInfo, type ImageBase } from "@/lib/api";
import SearchBar from "@/components/SearchBar";
import ImageCard from "@/components/ImageCard";

const CAT_EMOJI: Record<string, string> = {
  "Technology": "💻", "Finance": "💰", "Social & Content": "📱",
  "Learning": "📚", "Personal": "💬", "Maps & Places": "🗺️",
  "Media & Entertainment": "🎬", "Other": "📁",
};

export default function HomePage() {
  const [status, setStatus] = useState<ProcessStatus | null>(null);
  const [categories, setCategories] = useState<CategoryInfo[]>([]);
  const [recent, setRecent] = useState<ImageBase[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getStatus().catch(() => null),
      api.getCategories().catch(() => []),
      api.getImages({ limit: 10, status: "classified" }).catch(() => []),
    ]).then(([s, c, r]) => {
      setStatus(s);
      setCategories(c);
      setRecent(r);
      setLoading(false);
    });
  }, []);

  const topCats = categories.filter((c) => c.count > 0).slice(0, 8);

  return (
    <div className="min-h-screen">
      {/* Hero */}
      <section className="flex flex-col items-center justify-center px-6 py-24 text-center">
        <div className="mb-6">
          <span className="text-7xl">📸</span>
        </div>
        <h1 className="text-4xl md:text-5xl font-bold text-zinc-100 mb-3">
          Your Screenshot Library
        </h1>
        <p className="text-zinc-500 text-lg mb-10 max-w-lg">
          Search thousands of screenshots instantly. Auto-organised by topic,
          powered by OCR and semantic AI.
        </p>
        <SearchBar autoFocus />
      </section>

      {/* Stats bar */}
      {status && (
        <section className="max-w-5xl mx-auto px-6 pb-12">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: "Total Screenshots", value: status.total.toLocaleString() },
              { label: "Processed", value: status.done.toLocaleString() },
              { label: "Pending", value: status.remaining.toLocaleString() },
              { label: "Categories", value: categories.length.toString() },
            ].map((stat) => (
              <div
                key={stat.label}
                className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4 text-center"
              >
                <p className="text-2xl font-bold text-indigo-400">{stat.value}</p>
                <p className="text-xs text-zinc-500 mt-1">{stat.label}</p>
              </div>
            ))}
          </div>
          {status.running && (
            <div className="mt-4 flex items-center gap-3 p-3 rounded-xl bg-indigo-900/30 border border-indigo-800 text-indigo-300 text-sm">
              <span className="animate-spin">⚙️</span>
              <span>
                Pipeline running — Stage: <strong>{status.current_stage}</strong>
                {" "}({status.done}/{status.total})
              </span>
            </div>
          )}
        </section>
      )}

      {/* Category grid */}
      {topCats.length > 0 && (
        <section className="max-w-5xl mx-auto px-6 pb-12">
          <h2 className="text-lg font-semibold text-zinc-300 mb-4">Browse by Category</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {topCats.map((cat) => (
              <Link
                key={cat.name}
                href={`/library?category=${encodeURIComponent(cat.name)}`}
                className="rounded-2xl border border-zinc-800 bg-zinc-900 hover:border-indigo-600 hover:bg-zinc-800 p-4 transition-all group"
              >
                <span className="text-3xl">{CAT_EMOJI[cat.name] ?? "📁"}</span>
                <p className="text-sm font-medium text-zinc-200 mt-2">{cat.name}</p>
                <p className="text-xs text-zinc-500 mt-0.5">{cat.count} screenshots</p>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Recent screenshots */}
      {recent.length > 0 && (
        <section className="max-w-5xl mx-auto px-6 pb-16">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-zinc-300">Recently Processed</h2>
            <Link href="/library" className="text-sm text-indigo-400 hover:text-indigo-300">
              View all →
            </Link>
          </div>
          <div className="flex gap-4 overflow-x-auto pb-2">
            {recent.map((img) => (
              <div key={img.id} className="shrink-0 w-48">
                <ImageCard image={img} />
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Empty state */}
      {!loading && status?.total === 0 && (
        <section className="max-w-lg mx-auto px-6 pb-24 text-center">
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-8">
            <span className="text-5xl">🚀</span>
            <h2 className="text-xl font-semibold text-zinc-200 mt-4 mb-2">
              No screenshots yet
            </h2>
            <p className="text-zinc-500 text-sm mb-4">
              Run the pipeline to ingest and index your screenshot folder.
            </p>
            <code className="block bg-zinc-950 text-indigo-400 text-xs p-3 rounded-xl text-left">
              python -m backend.run_pipeline process-all<br />
              --source "C:\path\to\screenshots"
            </code>
          </div>
        </section>
      )}
    </div>
  );
}
