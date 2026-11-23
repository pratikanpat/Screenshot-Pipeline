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
    <html lang="en">
      <body>
        <div className="app-shell">
          <AppSidebar />
          <main className="app-main">{children}</main>
        </div>
      </body>
    </html>
  );
}
