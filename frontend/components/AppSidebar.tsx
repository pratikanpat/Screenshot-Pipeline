"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Camera,
  Home,
  Search,
  LayoutGrid,
  Tag,
  ChevronRight,
  CheckCircle2,
} from "lucide-react";
import { api, type CategoryInfo, type ProcessStatus } from "@/lib/api";

const NAV = [
  { href: "/",        label: "Overview",  icon: Home },
  { href: "/search",  label: "Search",    icon: Search },
  { href: "/library", label: "Library",   icon: LayoutGrid },
];

export default function AppSidebar() {
  const path = usePathname();
  const [categories, setCategories] = useState<CategoryInfo[]>([]);
  const [status, setStatus] = useState<ProcessStatus | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    api.getCategories().then(setCategories).catch(() => {});
    api.getStatus().then(setStatus).catch(() => {});
  }, []);

  const toggle = (name: string) =>
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });

  const isActive = (href: string) =>
    href === "/" ? path === "/" : path.startsWith(href);

  const catParam = typeof window !== "undefined"
    ? new URLSearchParams(window.location.search).get("category") ?? ""
    : "";

  return (
    <aside className="app-sidebar">
      {/* Logo */}
      <div style={{ padding: "20px 16px 16px", borderBottom: "1px solid var(--border)" }}>
        <Link
          href="/"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            textDecoration: "none",
          }}
        >
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: "var(--accent-soft)",
              border: "1px solid var(--accent)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <Camera size={16} color="var(--accent-hover)" />
          </div>
          <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)", letterSpacing: "-0.01em" }}>
            ScreenshotKB
          </span>
        </Link>
      </div>

      {/* Main nav */}
      <div style={{ padding: "12px 8px", flex: 1 }}>
        <p className="section-label" style={{ marginBottom: 6 }}>Workspace</p>
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {NAV.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={`nav-item ${isActive(href) ? "active" : ""}`}
            >
              <Icon size={15} />
              {label}
            </Link>
          ))}
        </div>

        {/* Categories section */}
        {categories.length > 0 && (
          <div style={{ marginTop: 20 }}>
            <p className="section-label" style={{ marginBottom: 6 }}>Browse</p>
            <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
              {/* All */}
              <Link
                href="/library"
                className={`nav-item ${path === "/library" && !catParam ? "active" : ""}`}
              >
                <Tag size={15} />
                All screenshots
              </Link>

              {/* Per category */}
              {categories.map(cat => (
                <div key={cat.name}>
                  <div style={{ display: "flex", alignItems: "center" }}>
                    <Link
                      href={`/library?category=${encodeURIComponent(cat.name)}`}
                      className={`nav-item ${catParam === cat.name ? "active" : ""}`}
                      style={{ flex: 1, minWidth: 0 }}
                    >
                      <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {cat.name}
                      </span>
                      <span style={{ fontSize: 11, color: "var(--text-faint)", fontFamily: "monospace", flexShrink: 0 }}>
                        {cat.count.toLocaleString()}
                      </span>
                    </Link>
                    {cat.subcategories.length > 0 && (
                      <button
                        onClick={() => toggle(cat.name)}
                        style={{
                          padding: "6px 4px",
                          background: "none",
                          border: "none",
                          cursor: "pointer",
                          color: "var(--text-faint)",
                          display: "flex",
                          alignItems: "center",
                          borderRadius: 4,
                          flexShrink: 0,
                        }}
                      >
                        <ChevronRight
                          size={12}
                          style={{
                            transition: "transform 150ms ease",
                            transform: expanded.has(cat.name) ? "rotate(90deg)" : "rotate(0deg)",
                          }}
                        />
                      </button>
                    )}
                  </div>

                  {/* Subcategories */}
                  {expanded.has(cat.name) && cat.subcategories.length > 0 && (
                    <div style={{ paddingLeft: 16, display: "flex", flexDirection: "column", gap: 1 }}>
                      {cat.subcategories.map(sub => (
                        <Link
                          key={sub.name}
                          href={`/library?category=${encodeURIComponent(cat.name)}&subcategory=${encodeURIComponent(sub.name)}`}
                          className="nav-item"
                          style={{ fontSize: 12.5, paddingTop: 5, paddingBottom: 5 }}
                        >
                          <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {sub.name}
                          </span>
                          <span style={{ fontSize: 11, color: "var(--text-faint)", fontFamily: "monospace", flexShrink: 0 }}>
                            {sub.count}
                          </span>
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Library status footer */}
      <div
        style={{
          padding: "12px 16px",
          borderTop: "1px solid var(--border)",
          display: "flex",
          flexDirection: "column",
          gap: 4,
        }}
      >
        {status && (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span className="status-dot green" />
              <span style={{ fontSize: 11, color: "var(--text-faint)", fontFamily: "monospace" }}>
                {status.total.toLocaleString()} items
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <CheckCircle2 size={11} color="var(--success)" />
              <span style={{ fontSize: 11, color: "var(--text-faint)", fontFamily: "monospace" }}>
                {status.done.toLocaleString()} indexed
              </span>
            </div>
          </>
        )}
      </div>
    </aside>
  );
}
