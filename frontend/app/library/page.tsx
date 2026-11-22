"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { api, type CategoryInfo, type ImageBase } from "@/lib/api";
import Sidebar from "@/components/Sidebar";
import ImageGrid from "@/components/ImageGrid";

function LibraryInner() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [categories, setCategories] = useState<CategoryInfo[]>([]);
  const [images, setImages] = useState<ImageBase[]>([]);
  const [loading, setLoading] = useState(true);

  const selectedCategory = searchParams.get("category") ?? "";
  const selectedSubcategory = searchParams.get("subcategory") ?? "";

  useEffect(() => {
    api.getCategories().then(setCategories).catch(() => []);
  }, []);

  useEffect(() => {
    setLoading(true);
    const fetch = selectedCategory
      ? api.getCategoryImages(selectedCategory, {
          subcategory: selectedSubcategory || undefined,
          limit: 60,
        })
      : api.getImages({ limit: 60 });

    fetch
      .then(setImages)
      .catch(() => setImages([]))
      .finally(() => setLoading(false));
  }, [selectedCategory, selectedSubcategory]);

  const handleSelect = (cat: string, sub?: string) => {
    const qs = new URLSearchParams();
    if (cat) qs.set("category", cat);
    if (sub) qs.set("subcategory", sub);
    router.push(`/library?${qs}`);
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 flex gap-8">
      {/* Sidebar */}
      <Sidebar
        categories={categories}
        selectedCategory={selectedCategory}
        selectedSubcategory={selectedSubcategory}
        onSelect={handleSelect}
      />

      {/* Main content */}
      <div className="flex-1 min-w-0 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-zinc-200">
            {selectedCategory ? (
              <>
                {selectedCategory}
                {selectedSubcategory && (
                  <span className="text-zinc-500 font-normal text-base ml-2">
                    / {selectedSubcategory}
                  </span>
                )}
              </>
            ) : (
              "All Screenshots"
            )}
          </h1>
          {!loading && (
            <span className="text-sm text-zinc-600">{images.length} screenshots</span>
          )}
        </div>

        {/* Grid */}
        <ImageGrid images={images} loading={loading} />
      </div>
    </div>
  );
}

export default function LibraryPage() {
  return (
    <Suspense>
      <LibraryInner />
    </Suspense>
  );
}
