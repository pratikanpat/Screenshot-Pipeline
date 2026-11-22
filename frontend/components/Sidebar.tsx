"use client";

import { useState } from "react";
import type { CategoryInfo } from "@/lib/api";

const CAT_EMOJI: Record<string, string> = {
  "Technology": "💻",
  "Finance": "💰",
  "Social & Content": "📱",
  "Learning": "📚",
  "Personal": "💬",
  "Maps & Places": "🗺️",
  "Media & Entertainment": "🎬",
  "Other": "📁",
};

interface Props {
  categories: CategoryInfo[];
  selectedCategory: string | null;
  selectedSubcategory: string | null;
  onSelect: (cat: string, sub?: string) => void;
}

export default function Sidebar({
  categories,
  selectedCategory,
  selectedSubcategory,
  onSelect,
}: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggle = (cat: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(cat) ? next.delete(cat) : next.add(cat);
      return next;
    });
  };

  return (
    <aside className="w-64 shrink-0 space-y-1">
      <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wider px-2 pb-2">
        Categories
      </p>

      {/* All */}
      <button
        onClick={() => onSelect("", undefined)}
        className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition ${
          !selectedCategory
            ? "bg-indigo-600 text-white"
            : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
        }`}
      >
        <span>🏠 All screenshots</span>
        <span className="text-xs opacity-60">
          {categories.reduce((s, c) => s + c.count, 0)}
        </span>
      </button>

      {categories.map((cat) => (
        <div key={cat.name}>
          {/* Category row */}
          <button
            onClick={() => {
              toggle(cat.name);
              onSelect(cat.name, undefined);
            }}
            className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition ${
              selectedCategory === cat.name && !selectedSubcategory
                ? "bg-indigo-600 text-white"
                : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
            }`}
          >
            <span>
              {CAT_EMOJI[cat.name] ?? "📂"} {cat.name}
            </span>
            <span className="flex items-center gap-1 text-xs opacity-60">
              {cat.count}
              {cat.subcategories.length > 0 && (
                <span>{expanded.has(cat.name) ? "▴" : "▾"}</span>
              )}
            </span>
          </button>

          {/* Subcategories */}
          {expanded.has(cat.name) && cat.subcategories.length > 0 && (
            <div className="pl-4 mt-0.5 space-y-0.5">
              {cat.subcategories.map((sub) => (
                <button
                  key={sub.name}
                  onClick={() => onSelect(cat.name, sub.name)}
                  className={`w-full flex items-center justify-between px-3 py-1.5 rounded-lg text-xs transition ${
                    selectedSubcategory === sub.name
                      ? "bg-indigo-600/40 text-indigo-300"
                      : "text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"
                  }`}
                >
                  <span>{sub.name}</span>
                  <span className="opacity-60">{sub.count}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      ))}
    </aside>
  );
}
