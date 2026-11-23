"use client";

import Link from "next/link";
import { api, type ImageBase, type SearchResult } from "@/lib/api";

function getId(img: ImageBase | SearchResult): number {
  return "id" in img ? img.id : img.image_id;
}

function formatDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

interface Props {
  image: ImageBase | SearchResult;
  snippet?: string;
}

export default function ImageCard({ image, snippet }: Props) {
  const id = getId(image);
  const category = image.category ?? null;

  return (
    <Link href={`/image/${id}`} className="img-card">
      {/* Thumbnail — object-fit: contain, never crop */}
      <div className="img-card-thumb">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={api.thumbnailUrl(id)}
          alt={image.filename}
          loading="lazy"
          onError={e => {
            const el = e.target as HTMLImageElement;
            el.style.display = "none";
            (el.parentElement as HTMLElement).innerHTML =
              `<div style="color:var(--text-faint);font-size:12px;">No preview</div>`;
          }}
        />
      </div>

      {/* Meta */}
      <div className="img-card-meta">
        {/* Category badge */}
        {category && <span className="cat-badge">{category}</span>}

        {/* OCR snippet */}
        {snippet && (
          <p
            className="snippet-text"
            style={{
              fontSize: 11.5,
              color: "var(--text-muted)",
              lineHeight: 1.5,
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}
            dangerouslySetInnerHTML={{ __html: snippet }}
          />
        )}

        {/* Date */}
        {image.captured_at && (
          <span
            className="font-mono"
            style={{ fontSize: 11, color: "var(--text-faint)" }}
          >
            {formatDate(image.captured_at)}
          </span>
        )}
      </div>
    </Link>
  );
}
