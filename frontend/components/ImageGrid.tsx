"use client";

import { type ImageBase, type SearchResult } from "@/lib/api";
import ImageCard from "./ImageCard";

interface Props {
  images: (ImageBase | SearchResult)[];
  loading?: boolean;
  snippets?: Record<number, string>;
}

function SkeletonCard() {
  return (
    <div className="rounded-2xl overflow-hidden border border-zinc-800 bg-zinc-900 animate-pulse">
      <div className="w-full aspect-video bg-zinc-800" />
      <div className="p-3 space-y-2">
        <div className="h-2 bg-zinc-800 rounded w-3/4" />
        <div className="h-2 bg-zinc-800 rounded w-1/2" />
      </div>
    </div>
  );
}

function getId(img: ImageBase | SearchResult): number {
  return "id" in img ? img.id : img.image_id;
}

export default function ImageGrid({ images, loading, snippets }: Props) {
  if (loading) {
    return (
      <div className="columns-1 sm:columns-2 lg:columns-3 xl:columns-4 gap-4 space-y-4">
        {Array.from({ length: 12 }).map((_, i) => (
          <div key={i} className="break-inside-avoid">
            <SkeletonCard />
          </div>
        ))}
      </div>
    );
  }

  if (images.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <span className="text-6xl mb-4">🔍</span>
        <p className="text-zinc-400 text-lg font-medium">No screenshots found</p>
        <p className="text-zinc-600 text-sm mt-1">
          Try a different search term or browse the library
        </p>
      </div>
    );
  }

  return (
    <div className="columns-1 sm:columns-2 lg:columns-3 xl:columns-4 gap-4 space-y-4">
      {images.map((img) => {
        const id = getId(img);
        return (
          <div key={id} className="break-inside-avoid">
            <ImageCard
              image={img}
              snippet={snippets?.[id] ?? ("snippet" in img ? img.snippet : undefined)}
            />
          </div>
        );
      })}
    </div>
  );
}
