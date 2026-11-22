"use client";

import Link from "next/link";
import { api, type ImageBase, type SearchResult } from "@/lib/api";

// Category → colour
const CAT_COLOURS: Record<string, string> = {
  "Technology": "bg-blue-900/60 text-blue-300 border-blue-800",
  "Finance": "bg-emerald-900/60 text-emerald-300 border-emerald-800",
  "Social & Content": "bg-purple-900/60 text-purple-300 border-purple-800",
  "Learning": "bg-amber-900/60 text-amber-300 border-amber-800",
  "Personal": "bg-pink-900/60 text-pink-300 border-pink-800",
  "Maps & Places": "bg-teal-900/60 text-teal-300 border-teal-800",
  "Media & Entertainment": "bg-orange-900/60 text-orange-300 border-orange-800",
  "Other": "bg-zinc-800 text-zinc-400 border-zinc-700",
};

function categoryColour(cat?: string | null) {
  return cat && CAT_COLOURS[cat]
    ? CAT_COLOURS[cat]
    : "bg-zinc-800 text-zinc-400 border-zinc-700";
}

interface Props {
  image: ImageBase | SearchResult;
  snippet?: string;
}

function getId(img: ImageBase | SearchResult): number {
  return "id" in img ? img.id : img.image_id;
}

export default function ImageCard({ image, snippet }: Props) {
  const id = getId(image);
  const tags: string[] = image.tags ?? [];
  const category = image.category ?? null;

  return (
    <Link
      href={`/image/${id}`}
      className="group block rounded-2xl overflow-hidden border border-zinc-800 bg-zinc-900 hover:border-indigo-600 hover:shadow-lg hover:shadow-indigo-900/20 transition-all duration-200"
    >
      {/* Thumbnail */}
      <div className="relative w-full aspect-video bg-zinc-800 overflow-hidden">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={api.thumbnailUrl(id)}
          alt={image.filename}
          loading="lazy"
          className="w-full h-full object-cover group-hover:scale-[1.03] transition-transform duration-300"
          onError={(e) => {
            (e.target as HTMLImageElement).style.opacity = "0";
          }}
        />
        {/* Category badge */}
        {category && (
          <span
            className={`absolute top-2 left-2 text-[10px] font-semibold px-2 py-0.5 rounded-full border ${categoryColour(category)}`}
          >
            {category}
          </span>
        )}
      </div>

      {/* Meta */}
      <div className="p-3 space-y-1.5">
        {/* Filename */}
        <p className="text-xs text-zinc-500 truncate">{image.filename}</p>

        {/* Snippet (search results) */}
        {snippet && (
          <p
            className="text-xs text-zinc-400 line-clamp-2 leading-relaxed"
            dangerouslySetInnerHTML={{ __html: snippet }}
          />
        )}

        {/* Tags */}
        {tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {tags.slice(0, 4).map((tag) => (
              <span
                key={tag}
                className="text-[10px] px-1.5 py-0.5 rounded-md bg-zinc-800 text-zinc-500"
              >
                {tag}
              </span>
            ))}
          </div>
        )}

        {/* Date */}
        {image.captured_at && (
          <p className="text-[10px] text-zinc-600">
            {new Date(image.captured_at).toLocaleDateString("en-IN", {
              day: "numeric",
              month: "short",
              year: "numeric",
            })}
          </p>
        )}
      </div>
    </Link>
  );
}
