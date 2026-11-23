"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Layers } from "lucide-react";
import { api, type ProcessStatus, type CategoryInfo, type ImageBase } from "@/lib/api";
import SearchBar from "@/components/SearchBar";
import ImageCard from "@/components/ImageCard";

function getHour(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

export default function HomePage() {
  const [status, setStatus] = useState<ProcessStatus | null>(null);
  const [categories, setCategories] = useState<CategoryInfo[]>([]);
  const [recent, setRecent] = useState<ImageBase[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getStatus().catch(() => null),
      api.getCategories().catch(() => [] as CategoryInfo[]),
      api.getImages({ limit: 8, status: "classified" }).catch(() => [] as ImageBase[]),
    ]).then(([s, c, r]) => {
      setStatus(s);
      setCategories(c);
      setRecent(r);
      setLoading(false);
    });
  }, []);

  const topCats = categories.filter(c => c.count > 0);

  return (
    <div className="page-content" style={{ maxWidth: 900 }}>
      {/* Greeting */}
      <div style={{ marginBottom: 28 }}>
        <p style={{ fontSize: 13, color: "var(--text-faint)", marginBottom: 4, fontFamily: "monospace" }}>
          {getHour()}
        </p>
        <h1 style={{ fontSize: 24, fontWeight: 600, color: "var(--text-primary)", margin: 0, letterSpacing: "-0.02em" }}>
          Your archive is ready.
        </h1>
      </div>

      {/* Search — primary action */}
      <div style={{ marginBottom: 36 }}>
        <SearchBar autoFocus />
      </div>

      {/* Stats strip */}
      {status && (
        <div
          style={{
            display: "flex",
            gap: 24,
            marginBottom: 36,
            padding: "12px 16px",
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            borderRadius: 8,
          }}
        >
          {[
            { label: "Total",      value: status.total.toLocaleString() },
            { label: "Indexed",    value: status.done.toLocaleString() },
            { label: "Pending",    value: status.remaining.toLocaleString() },
            { label: "Categories", value: categories.length.toString() },
          ].map(stat => (
            <div key={stat.label} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              <span
                className="font-mono"
                style={{ fontSize: 18, fontWeight: 600, color: "var(--text-primary)" }}
              >
                {stat.value}
              </span>
              <span style={{ fontSize: 11, color: "var(--text-faint)" }}>{stat.label}</span>
            </div>
          ))}

          {status.running && (
            <div
              style={{
                marginLeft: "auto",
                display: "flex",
                alignItems: "center",
                gap: 6,
                fontSize: 12,
                color: "var(--accent-hover)",
              }}
            >
              <div
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: "50%",
                  background: "var(--accent)",
                  animation: "pulse 2s infinite",
                }}
              />
              {status.current_stage} running…
            </div>
          )}
        </div>
      )}

      {/* Categories */}
      {topCats.length > 0 && (
        <section style={{ marginBottom: 36 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
              <Layers size={14} color="var(--text-faint)" />
              <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-muted)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
                Categories
              </span>
            </div>
            <Link
              href="/library"
              style={{ fontSize: 12, color: "var(--accent-hover)", textDecoration: "none", display: "flex", alignItems: "center", gap: 3 }}
            >
              View all <ArrowRight size={12} />
            </Link>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
              gap: 8,
            }}
          >
            {topCats.map(cat => (
              <Link
                key={cat.name}
                href={`/library?category=${encodeURIComponent(cat.name)}`}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "10px 14px",
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  textDecoration: "none",
                  transition: "border-color 150ms ease, background 150ms ease",
                  gap: 8,
                }}
                onMouseEnter={e => {
                  (e.currentTarget as HTMLElement).style.borderColor = "var(--border-strong)";
                  (e.currentTarget as HTMLElement).style.background = "var(--bg-elevated)";
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLElement).style.borderColor = "var(--border)";
                  (e.currentTarget as HTMLElement).style.background = "var(--bg-surface)";
                }}
              >
                <span style={{ fontSize: 13, color: "var(--text-primary)", fontWeight: 450, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {cat.name}
                </span>
                <span className="font-mono" style={{ fontSize: 11, color: "var(--text-faint)", flexShrink: 0 }}>
                  {cat.count.toLocaleString()}
                </span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Recent */}
      {!loading && recent.length > 0 && (
        <section>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-muted)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
              Recently Processed
            </span>
            <Link
              href="/library"
              style={{ fontSize: 12, color: "var(--accent-hover)", textDecoration: "none", display: "flex", alignItems: "center", gap: 3 }}
            >
              View all <ArrowRight size={12} />
            </Link>
          </div>
          <div className="recent-strip">
            {recent.map(img => (
              <div key={img.id} style={{ width: 160, flexShrink: 0 }}>
                <ImageCard image={img} />
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Empty state */}
      {!loading && (!status || status.total === 0) && (
        <div
          style={{
            padding: 32,
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            borderRadius: 10,
            textAlign: "center",
          }}
        >
          <p style={{ fontSize: 15, color: "var(--text-muted)", fontWeight: 500, marginBottom: 8 }}>
            No screenshots indexed yet
          </p>
          <p style={{ fontSize: 13, color: "var(--text-faint)", marginBottom: 16 }}>
            Run the pipeline to ingest your screenshot folder.
          </p>
          <code
            style={{
              display: "block",
              background: "var(--bg-elevated)",
              color: "var(--accent-hover)",
              fontSize: 12,
              padding: "12px 16px",
              borderRadius: 8,
              textAlign: "left",
              fontFamily: "monospace",
            }}
          >
            python -m backend.run_pipeline process-all --source &quot;C:\path\to\screenshots&quot;
          </code>
        </div>
      )}
    </div>
  );
}
