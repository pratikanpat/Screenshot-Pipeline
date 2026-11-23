"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { api, type CategoryInfo, type ImageBase } from "@/lib/api";
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
    api.getCategories().then(setCategories).catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    const fetchFn = selectedCategory
      ? api.getCategoryImages(selectedCategory, {
          subcategory: selectedSubcategory || undefined,
          limit: 80,
        })
      : api.getImages({ limit: 80 });

    fetchFn
      .then(setImages)
      .catch(() => setImages([]))
      .finally(() => setLoading(false));
  }, [selectedCategory, selectedSubcategory]);

  const selectCat = (cat: string, sub?: string) => {
    const qs = new URLSearchParams();
    if (cat) qs.set("category", cat);
    if (sub) qs.set("subcategory", sub);
    router.push(`/library?${qs}`);
  };

  /* Active category object for subcategory chips */
  const activeCat = categories.find(c => c.name === selectedCategory);

  return (
    <div className="page-content" style={{ maxWidth: 1200 }}>
      {/* Page header */}
      <div style={{ marginBottom: 20 }}>
        <h1
          style={{
            fontSize: 22,
            fontWeight: 600,
            color: "var(--text-primary)",
            margin: 0,
            letterSpacing: "-0.02em",
          }}
        >
          {selectedCategory || "All Screenshots"}
          {selectedSubcategory && (
            <span style={{ color: "var(--text-muted)", fontWeight: 400, fontSize: 16, marginLeft: 8 }}>
              / {selectedSubcategory}
            </span>
          )}
        </h1>
        {!loading && (
          <p className="font-mono" style={{ fontSize: 12, color: "var(--text-faint)", marginTop: 4 }}>
            {images.length.toLocaleString()} screenshots
          </p>
        )}
      </div>

      {/* Category filter chips */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 6,
          marginBottom: 20,
        }}
      >
        <button
          onClick={() => selectCat("")}
          className={`chip ${!selectedCategory ? "active" : ""}`}
        >
          All
        </button>
        {categories.map(cat => (
          <button
            key={cat.name}
            onClick={() => selectCat(cat.name)}
            className={`chip ${selectedCategory === cat.name ? "active" : ""}`}
          >
            {cat.name}
            <span className="font-mono" style={{ fontSize: 10, opacity: 0.7 }}>
              {cat.count.toLocaleString()}
            </span>
          </button>
        ))}
      </div>

      {/* Subcategory chips (only when a category is selected) */}
      {activeCat && activeCat.subcategories.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: 20 }}>
          <button
            onClick={() => selectCat(selectedCategory)}
            className={`chip ${!selectedSubcategory ? "active" : ""}`}
            style={{ fontSize: 11.5 }}
          >
            All {selectedCategory}
          </button>
          {activeCat.subcategories.map(sub => (
            <button
              key={sub.name}
              onClick={() => selectCat(selectedCategory, sub.name)}
              className={`chip ${selectedSubcategory === sub.name ? "active" : ""}`}
              style={{ fontSize: 11.5 }}
            >
              {sub.name}
              <span className="font-mono" style={{ fontSize: 10, opacity: 0.7 }}>
                {sub.count}
              </span>
            </button>
          ))}
        </div>
      )}

      {/* Grid */}
      <ImageGrid
        images={images}
        loading={loading}
        emptyMessage="No screenshots in this category"
        emptyHint="Try browsing a different category or search"
      />
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
