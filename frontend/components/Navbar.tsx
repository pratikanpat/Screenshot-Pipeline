"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Home" },
  { href: "/search", label: "Search" },
  { href: "/library", label: "Library" },
];

export default function Navbar() {
  const path = usePathname();

  return (
    <nav className="fixed top-0 inset-x-0 z-50 h-16 border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-md flex items-center px-6 gap-8">
      {/* Logo */}
      <Link href="/" className="flex items-center gap-2 font-bold text-lg shrink-0">
        <span className="text-2xl">📸</span>
        <span className="text-zinc-100">ScreenshotKB</span>
      </Link>

      {/* Nav links */}
      <div className="flex items-center gap-1">
        {links.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              path === l.href
                ? "bg-indigo-600 text-white"
                : "text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800"
            }`}
          >
            {l.label}
          </Link>
        ))}
      </div>
    </nav>
  );
}

