import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Navbar from "@/components/Navbar";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "ScreenshotKB — Your Personal Screenshot Library",
  description:
    "Search, browse and auto-organise your screenshot collection. Keyword search, semantic search, auto-categorisation.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen bg-zinc-950 text-zinc-100">
        <Navbar />
        <main className="pt-16">{children}</main>
      </body>
    </html>
  );
}
