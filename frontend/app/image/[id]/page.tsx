"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api, type ImageDetail } from "@/lib/api";

export default function ImageDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params.id);

  const [image, setImage] = useState<ImageDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [imgError, setImgError] = useState(false);

  useEffect(() => {
    if (!id) return;
    api.getImage(id)
      .then(setImage)
      .catch(() => setImage(null))
      .finally(() => setLoading(false));
  }, [id]);

  const copyText = () => {
    if (!image?.extracted_text) return;
    navigator.clipboard.writeText(image.extracted_text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto px-6 py-12 animate-pulse space-y-4">
        <div className="h-8 bg-zinc-800 rounded w-1/3" />
        <div className="h-96 bg-zinc-800 rounded-2xl" />
      </div>
    );
  }

  if (!image) {
    return (
      <div className="max-w-2xl mx-auto px-6 py-24 text-center">
        <span className="text-5xl">😕</span>
        <p className="text-zinc-400 mt-4">Screenshot not found.</p>
        <button onClick={() => router.back()} className="mt-4 text-indigo-400 hover:underline text-sm">
          ← Go back
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      {/* Back */}
      <button
        onClick={() => router.back()}
        className="text-sm text-zinc-500 hover:text-zinc-300 mb-6 flex items-center gap-1 transition"
      >
        ← Back
      </button>

      <div className="flex flex-col lg:flex-row gap-8">
        {/* Image panel */}
        <div className="flex-1 min-w-0">
          <div className="rounded-2xl overflow-hidden border border-zinc-800 bg-zinc-900">
            {!imgError ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={api.fileUrl(id)}
                alt={image.filename}
                className="w-full h-auto max-h-[80vh] object-contain"
                onError={() => setImgError(true)}
              />
            ) : (
              <div className="flex items-center justify-center h-64 text-zinc-600 text-sm">
                Image file not accessible
              </div>
            )}
          </div>

          {/* Filename */}
          <p className="text-xs text-zinc-600 mt-2 px-1 truncate">{image.filename}</p>
        </div>

        {/* Meta panel */}
        <aside className="lg:w-80 shrink-0 space-y-4">
          {/* Category */}
          {image.category && (
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4 space-y-2">
              <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Category</p>
              <div className="flex flex-wrap gap-2">
                <span className="px-2 py-1 rounded-lg bg-indigo-900/50 text-indigo-300 text-sm border border-indigo-800">
                  {image.category}
                </span>
                {image.subcategory && (
                  <span className="px-2 py-1 rounded-lg bg-zinc-800 text-zinc-400 text-sm">
                    {image.subcategory}
                  </span>
                )}
                {image.content_type && (
                  <span className="px-2 py-1 rounded-lg bg-zinc-800 text-zinc-500 text-xs">
                    {image.content_type}
                  </span>
                )}
              </div>
              {image.tags && image.tags.length > 0 && (
                <div className="flex flex-wrap gap-1 pt-1">
                  {image.tags.map((tag) => (
                    <Link
                      key={tag}
                      href={`/search?q=${encodeURIComponent(tag)}&mode=keyword`}
                      className="text-[11px] px-2 py-0.5 rounded-md bg-zinc-800 text-zinc-500 hover:text-indigo-400 hover:bg-zinc-700 transition"
                    >
                      {tag}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* File info */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4 space-y-2">
            <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">File Info</p>
            {[
              ["Captured", image.captured_at ? new Date(image.captured_at).toLocaleString("en-IN") : "Unknown"],
              ["Dimensions", image.width && image.height ? `${image.width} × ${image.height}` : "—"],
              ["Size", image.file_size ? `${(image.file_size / 1024).toFixed(0)} KB` : "—"],
              ["OCR Engine", image.engine ?? "—"],
              ["OCR Confidence", image.ocr_confidence ? `${image.ocr_confidence.toFixed(1)}%` : "—"],
              ["Words found", image.word_count?.toString() ?? "—"],
              ["Method", image.method ?? "—"],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between text-xs">
                <span className="text-zinc-600">{k}</span>
                <span className="text-zinc-400 text-right max-w-[60%] truncate">{v}</span>
              </div>
            ))}
          </div>

          {/* OCR text */}
          {image.extracted_text && (
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4 space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
                  Extracted Text
                </p>
                <button
                  onClick={copyText}
                  className="text-xs text-indigo-400 hover:text-indigo-300 transition"
                >
                  {copied ? "✓ Copied" : "Copy"}
                </button>
              </div>
              <div className="max-h-48 overflow-y-auto">
                <p className="text-xs text-zinc-400 leading-relaxed whitespace-pre-wrap">
                  {image.extracted_text}
                </p>
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
