"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Copy,
  Check,
  Calendar,
  Layers,
  FileText,
  Tag,
  Maximize2,
} from "lucide-react";
import { api, type ImageDetail } from "@/lib/api";

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function formatBytes(bytes: number | null): string {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

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

  /* ── Loading ── */
  if (loading) {
    return (
      <div className="page-content" style={{ maxWidth: 1200 }}>
        <div style={{ height: 20, width: 160, borderRadius: 6, marginBottom: 24 }} className="skeleton" />
        <div className="detail-layout">
          <div className="detail-image-col">
            <div style={{ height: 500, borderRadius: 10 }} className="skeleton" />
          </div>
          <div className="detail-meta-col">
            {[120, 200, 160].map((h, i) => (
              <div key={i} style={{ height: h, borderRadius: 10 }} className="skeleton" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  /* ── Not found ── */
  if (!image) {
    return (
      <div className="page-content" style={{ maxWidth: 480, textAlign: "center", paddingTop: 80 }}>
        <p style={{ fontSize: 15, color: "var(--text-muted)", marginBottom: 12 }}>Screenshot not found.</p>
        <button onClick={() => router.back()} className="btn btn-ghost">
          <ArrowLeft size={14} />
          Go back
        </button>
      </div>
    );
  }

  const tags: string[] = image.tags ?? [];

  return (
    <div className="page-content" style={{ maxWidth: 1200 }}>
      {/* Back breadcrumb */}
      <div style={{ marginBottom: 20 }}>
        <button onClick={() => router.back()} className="btn btn-ghost" style={{ padding: "5px 10px" }}>
          <ArrowLeft size={13} />
          Back
        </button>
      </div>

      <div className="detail-layout">
        {/* ── Image column ── */}
        <div className="detail-image-col">
          <div
            style={{
              background: "var(--bg-elevated)",
              border: "1px solid var(--border)",
              borderRadius: 10,
              overflow: "hidden",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              minHeight: 300,
              maxHeight: "80vh",
            }}
          >
            {!imgError ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={api.fileUrl(id)}
                alt={image.filename}
                style={{ maxWidth: "100%", maxHeight: "80vh", objectFit: "contain", display: "block" }}
                onError={() => setImgError(true)}
              />
            ) : (
              <div style={{ padding: 32, color: "var(--text-faint)", fontSize: 13, textAlign: "center" }}>
                <Maximize2 size={32} style={{ marginBottom: 8, opacity: 0.3 }} />
                <p>Image file not accessible</p>
                <p style={{ fontSize: 11, marginTop: 4 }}>{image.original_path}</p>
              </div>
            )}
          </div>

          {/* Filename */}
          <p
            className="font-mono"
            style={{ fontSize: 11, color: "var(--text-faint)", marginTop: 8, paddingLeft: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
          >
            {image.filename}
          </p>
        </div>

        {/* ── Meta column ── */}
        <div className="detail-meta-col">

          {/* Category + tags */}
          {(image.category || tags.length > 0) && (
            <div className="panel">
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 12 }}>
                <Layers size={13} color="var(--text-faint)" />
                <span className="section-label">Category</span>
              </div>
              {image.category && (
                <div style={{ marginBottom: tags.length > 0 ? 10 : 0 }}>
                  <span className="cat-badge" style={{ marginRight: 6, marginBottom: 4, display: "inline-block" }}>
                    {image.category}
                  </span>
                  {image.subcategory && (
                    <span
                      style={{
                        fontSize: 11,
                        color: "var(--text-muted)",
                        background: "var(--bg-elevated)",
                        border: "1px solid var(--border)",
                        borderRadius: 4,
                        padding: "2px 7px",
                        display: "inline-block",
                      }}
                    >
                      {image.subcategory}
                    </span>
                  )}
                </div>
              )}
              {tags.length > 0 && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
                  {tags.map(tag => (
                    <Link
                      key={tag}
                      href={`/search?q=${encodeURIComponent(tag)}&mode=keyword`}
                      style={{
                        fontSize: 11,
                        color: "var(--text-muted)",
                        background: "var(--bg-elevated)",
                        border: "1px solid var(--border)",
                        borderRadius: 4,
                        padding: "2px 7px",
                        textDecoration: "none",
                        transition: "color 150ms ease, border-color 150ms ease",
                        display: "flex",
                        alignItems: "center",
                        gap: 3,
                      }}
                      onMouseEnter={e => {
                        (e.currentTarget as HTMLElement).style.color = "var(--accent-hover)";
                        (e.currentTarget as HTMLElement).style.borderColor = "var(--accent)";
                      }}
                      onMouseLeave={e => {
                        (e.currentTarget as HTMLElement).style.color = "var(--text-muted)";
                        (e.currentTarget as HTMLElement).style.borderColor = "var(--border)";
                      }}
                    >
                      <Tag size={9} />
                      {tag}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* File info */}
          <div className="panel">
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 12 }}>
              <Calendar size={13} color="var(--text-faint)" />
              <span className="section-label">File Info</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {[
                ["Captured",    formatDate(image.captured_at)],
                ["Dimensions",  image.width && image.height ? `${image.width} × ${image.height} px` : "—"],
                ["File size",   formatBytes(image.file_size)],
                ["OCR engine",  image.engine ?? "—"],
                ["Confidence",  image.ocr_confidence ? `${image.ocr_confidence.toFixed(1)}%` : "—"],
                ["Words",       image.word_count?.toLocaleString() ?? "—"],
              ].map(([k, v]) => (
                <div key={k} className="meta-row">
                  <span className="meta-key">{k}</span>
                  <span className="meta-value font-mono">{v}</span>
                </div>
              ))}
            </div>
          </div>

          {/* OCR text */}
          {image.extracted_text && (
            <div className="panel">
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <FileText size={13} color="var(--text-faint)" />
                  <span className="section-label">OCR Text</span>
                </div>
                <button
                  onClick={copyText}
                  className="btn-icon"
                  title="Copy text"
                  style={{ border: "none" }}
                >
                  {copied ? (
                    <Check size={13} color="var(--success)" />
                  ) : (
                    <Copy size={13} />
                  )}
                </button>
              </div>
              <div
                style={{
                  maxHeight: 220,
                  overflowY: "auto",
                  padding: "10px 12px",
                  background: "var(--bg-elevated)",
                  borderRadius: 7,
                  border: "1px solid var(--border)",
                }}
              >
                <p
                  className="font-mono"
                  style={{
                    fontSize: 11.5,
                    color: "var(--text-muted)",
                    lineHeight: 1.7,
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    margin: 0,
                  }}
                >
                  {image.extracted_text}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
