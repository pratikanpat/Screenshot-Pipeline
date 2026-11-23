"use client";

import { Search } from "lucide-react";
import { type ImageBase, type SearchResult } from "@/lib/api";
import ImageCard from "./ImageCard";

function getId(img: ImageBase | SearchResult): number {
  return "id" in img ? img.id : img.image_id;
}

function SkeletonCard() {
  return (
    <div className="img-card" style={{ cursor: "default" }}>
      <div className="img-card-thumb skeleton" />
      <div className="img-card-meta" style={{ gap: 6 }}>
        <div className="skeleton" style={{ height: 16, width: "50%", borderRadius: 4 }} />
        <div className="skeleton" style={{ height: 11, width: "35%", borderRadius: 4 }} />
      </div>
    </div>
  );
}

interface Props {
  images: (ImageBase | SearchResult)[];
  loading?: boolean;
  snippets?: Record<number, string>;
  emptyMessage?: string;
  emptyHint?: string;
}

export default function ImageGrid({
  images,
  loading,
  snippets,
  emptyMessage = "No screenshots found",
  emptyHint = "Try a different search term or browse the library",
}: Props) {
  if (loading) {
    return (
      <div className="img-grid">
        {Array.from({ length: 15 }).map((_, i) => <SkeletonCard key={i} />)}
      </div>
    );
  }

  if (images.length === 0) {
    return (
      <div className="empty-state">
        <Search size={40} />
        <p className="empty-title">{emptyMessage}</p>
        <p className="empty-sub">{emptyHint}</p>
      </div>
    );
  }

  return (
    <div className="img-grid">
      {images.map(img => {
        const id = getId(img);
        return (
          <ImageCard
            key={id}
            image={img}
            snippet={snippets?.[id] ?? ("snippet" in img ? img.snippet : undefined)}
          />
        );
      })}
    </div>
  );
}
