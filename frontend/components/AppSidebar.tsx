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
  Sun,
  Moon,
} from "lucide-react";
import { api, type CategoryInfo, type ProcessStatus } from "@/lib/api";

const NAV = [
  { href: "/",        label: "Overview",  icon: Home },
  { href: "/search",  label: "Search",    icon: Search },
  { href: "/library", label: "Library",   icon: LayoutGrid },
];

/* Read the current theme from the <html> element */
function getTheme(): "dark" | "light" {
  if (typeof document === "undefined") return "dark";
  return (document.documentElement.getAttribute("data-theme") as "dark" | "light") ?? "dark";
}

export default function AppSidebar() {
  const path = usePathname();
  const [categories, setCategories] = useState<CategoryInfo[]>([]);
  const [status, setStatus] = useState<ProcessStatus | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  /* Load categories + status once */
  useEffect(() => {
    api.getCategories().then(setCategories).catch(() => {});
    api.getStatus().then(setStatus).catch(() => {});
  }, []);

  /* Sync theme state from DOM on mount */
  useEffect(() => {
    setTheme(getTheme());
  }, []);

  /* Toggle theme */
  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("skb-theme", next); } catch {}
  };

  const toggle = (name: string) =>
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });

  /* Active check — exact for home, prefix for others */
  const isActive = (href: string) =>
    href === "/" ? path === "/" : path.startsWith(href);

  /* Current category from URL */
  const catParam =
    typeof window !== "undefined"
      ? new URLSearchParams(window.location.search).get("category") ?? ""
      : "";

  return (
    <aside className="app-sidebar">

      {/* ── Logo ── */}
      <div
        style={{
          padding: "18px 14px 14px",
          borderBottom: "1px solid var(--border)",
          flexShrink: 0,
        }}
      >
        <Link
          href="/"
          style={{ display: "flex", alignItems: "center", gap: 9, textDecoration: "none" }}
        >
          <div
            style={{
              width: 30,
              height: 30,
              borderRadius: 7,
              background: "var(--accent-soft)",
              border: "1px solid var(--accent)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <Camera size={15} color="var(--accent)" />
          </div>
          <span
            style={{
              fontSize: 13.5,
              fontWeight: 600,
              color: "var(--text-primary)",
              letterSpacing: "-0.01em",
            }}
          >
            ScreenshotKB
          </span>
        </Link>
      </div>

      {/* ── Main nav ── */}
      <div style={{ padding: "10px 8px", flex: 1, overflowY: "auto" }}>

        {/* Primary nav — Workspace */}
        <p
          className="section-label"
          style={{ padding: "0 6px", marginBottom: 5, display: "block" }}
        >
          Workspace
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: 1, marginBottom: 18 }}>
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

        {/* Categories */}
        {categories.length > 0 && (
          <>
            <p
              className="section-label"
              style={{ padding: "0 6px", marginBottom: 5, display: "block" }}
            >
              Browse
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>

              {/* All screenshots */}
              <Link
                href="/library"
                className={`nav-item ${path === "/library" && !catParam ? "active" : ""}`}
              >
                <Tag size={14} />
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
                      <span
                        style={{
                          flex: 1,
                          minWidth: 0,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {cat.name}
                      </span>
                      <span
                        className="font-mono"
                        style={{ fontSize: 10.5, color: "var(--text-faint)", flexShrink: 0 }}
                      >
                        {cat.count.toLocaleString()}
                      </span>
                    </Link>

                    {/* Expand subcategories */}
                    {cat.subcategories.length > 0 && (
                      <button
                        onClick={() => toggle(cat.name)}
                        className="btn-icon"
                        style={{ padding: "4px 3px" }}
                        title="Show subcategories"
                      >
                        <ChevronRight
                          size={11}
                          style={{
                            transition: "transform 150ms ease",
                            transform: expanded.has(cat.name) ? "rotate(90deg)" : "none",
                          }}
                        />
                      </button>
                    )}
                  </div>

                  {/* Subcategory list */}
                  {expanded.has(cat.name) && cat.subcategories.length > 0 && (
                    <div style={{ paddingLeft: 14, display: "flex", flexDirection: "column", gap: 1 }}>
                      {cat.subcategories.map(sub => (
                        <Link
                          key={sub.name}
                          href={`/library?category=${encodeURIComponent(cat.name)}&subcategory=${encodeURIComponent(sub.name)}`}
                          className="nav-item"
                          style={{ fontSize: 12, paddingTop: 4, paddingBottom: 4 }}
                        >
                          <span
                            style={{
                              flex: 1,
                              minWidth: 0,
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {sub.name}
                          </span>
                          <span
                            className="font-mono"
                            style={{ fontSize: 10, color: "var(--text-faint)", flexShrink: 0 }}
                          >
                            {sub.count}
                          </span>
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {/* ── Footer — library status + theme toggle ── */}
      <div
        style={{
          padding: "10px 8px",
          borderTop: "1px solid var(--border)",
          display: "flex",
          flexDirection: "column",
          gap: 8,
          flexShrink: 0,
        }}
      >
        {/* Theme toggle */}
        <button onClick={toggleTheme} className="theme-toggle">
          {theme === "dark" ? (
            <>
              <Sun size={13} />
              <span>Light mode</span>
            </>
          ) : (
            <>
              <Moon size={13} />
              <span>Dark mode</span>
            </>
          )}
        </button>

        {/* Library status — tiny, faint, monospace */}
        {status && (
          <div style={{ padding: "0 2px", display: "flex", flexDirection: "column", gap: 3 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span className="status-dot green" />
              <span
                className="font-mono"
                style={{ fontSize: 10.5, color: "var(--text-faint)" }}
              >
                {status.total.toLocaleString()} items
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <CheckCircle2 size={10} color="var(--success)" />
              <span
                className="font-mono"
                style={{ fontSize: 10.5, color: "var(--text-faint)" }}
              >
                {status.done.toLocaleString()} indexed
              </span>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
