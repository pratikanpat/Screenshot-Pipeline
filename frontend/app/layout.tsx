import type { Metadata } from "next";
import "./globals.css";
import AppSidebar from "@/components/AppSidebar";

export const metadata: Metadata = {
  title: "ScreenshotKB — Your Personal Screenshot Archive",
  description:
    "Search, browse and auto-organise your screenshot collection. Keyword search, OCR-powered, auto-categorised.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" data-theme="dark">
      <head>
        {/*
          Inline script runs BEFORE React hydrates — sets the saved theme
          on <html> immediately so there's zero flash of wrong theme.
          Must be a blocking script (no defer/async).
        */}
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var saved = localStorage.getItem('skb-theme');
                  var theme = (saved === 'light' || saved === 'dark') ? saved : 'dark';
                  document.documentElement.setAttribute('data-theme', theme);
                } catch(e) {}
                // Add class AFTER a tick so transitions don't fire on load
                setTimeout(function() {
                  document.documentElement.classList.add('theme-ready');
                }, 100);
              })();
            `,
          }}
        />
      </head>
      <body>
        <div className="app-shell">
          <AppSidebar />
          <main className="app-main">{children}</main>
        </div>
      </body>
    </html>
  );
}
