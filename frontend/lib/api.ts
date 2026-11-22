// lib/api.ts — typed API client for the Screenshot Knowledge Base backend

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─── Types ───────────────────────────────────────────────────────────────────

export interface ImageBase {
  id: number;
  filename: string;
  original_path: string;
  width: number | null;
  height: number | null;
  captured_at: string | null;
  status: string;
  category?: string | null;
  subcategory?: string | null;
  tags?: string[];
}

export interface ImageDetail extends ImageBase {
  modified_at: string | null;
  file_size: number | null;
  sha256: string | null;
  extracted_text: string | null;
  language: string | null;
  ocr_confidence: number | null;
  engine: string | null;
  word_count: number | null;
  content_type: string | null;
  cat_confidence: number | null;
  method: string | null;
}

export interface SearchResult {
  image_id: number;
  filename: string;
  original_path: string;
  width: number | null;
  height: number | null;
  captured_at: string | null;
  category: string | null;
  subcategory: string | null;
  content_type: string | null;
  tags: string[];
  snippet: string;
  score: number;
  search_mode: string;
}

export interface SearchResponse {
  query: string;
  mode: string;
  total: number;
  results: SearchResult[];
  time_ms: number;
}

export interface SubcategoryInfo {
  name: string;
  count: number;
}

export interface CategoryInfo {
  name: string;
  subcategories: SubcategoryInfo[];
  count: number;
}

export interface ProcessStatus {
  running: boolean;
  total: number;
  done: number;
  remaining: number;
  eta_seconds: number | null;
  current_stage: string | null;
}

// ─── Fetch wrapper ────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    // No caching for local dev
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${path} → ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ─── API functions ────────────────────────────────────────────────────────────

export const api = {
  // Search
  search: (
    q: string,
    mode: "keyword" | "semantic" | "hybrid" = "keyword",
    limit = 20,
    offset = 0
  ): Promise<SearchResponse> =>
    apiFetch(
      `/search?q=${encodeURIComponent(q)}&mode=${mode}&limit=${limit}&offset=${offset}`
    ),

  // Images
  getImages: (params?: {
    limit?: number;
    offset?: number;
    status?: string;
  }): Promise<ImageBase[]> => {
    const qs = new URLSearchParams();
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    if (params?.status) qs.set("status", params.status);
    return apiFetch(`/images?${qs}`);
  },

  getImage: (id: number): Promise<ImageDetail> =>
    apiFetch(`/images/${id}`),

  thumbnailUrl: (id: number) => `${BASE_URL}/images/${id}/thumbnail`,
  fileUrl: (id: number) => `${BASE_URL}/images/${id}/file`,

  // Categories
  getCategories: (): Promise<CategoryInfo[]> => apiFetch("/categories"),

  getCategoryImages: (
    category: string,
    params?: { subcategory?: string; limit?: number; offset?: number }
  ): Promise<ImageBase[]> => {
    const qs = new URLSearchParams();
    if (params?.subcategory) qs.set("subcategory", params.subcategory);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    return apiFetch(
      `/categories/${encodeURIComponent(category)}/images?${qs}`
    );
  },

  getCategoryTree: (): Promise<Record<string, Record<string, number>>> =>
    apiFetch("/categories/tree"),

  // Process
  getStatus: (): Promise<ProcessStatus> => apiFetch("/process/status"),

  startPipeline: (body: {
    source: string;
    steps?: string[];
    limit?: number | null;
  }): Promise<{ message: string }> =>
    apiFetch("/process/start", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
