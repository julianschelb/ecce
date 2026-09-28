/** Typed API client. All requests are relative to the page origin ("/api/...") so the same
 *  build works behind the FastAPI static mount, the nginx proxy and the Vite dev proxy. */

export const TOKEN_KEY = "ecce.admin.token";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable */
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  form?: FormData;
  signal?: AbortSignal;
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (options.form) body = options.form;
  else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }
  const response = await fetch(path, { method: options.method ?? "GET", headers, body, signal: options.signal });
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!response.ok) {
    const detail =
      data && typeof data === "object" && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : response.statusText;
    throw new ApiError(response.status, detail);
  }
  return data as T;
}

export function query(params: Record<string, string | number | boolean | Array<string | number> | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => search.append(key, String(v)));
    else search.set(key, String(value));
  }
  const s = search.toString();
  return s ? `?${s}` : "";
}

// ---------------------------------------------------------------- types (mirror backend schemas)

export interface CorpusSummary {
  slug: string;
  title: string;
  author: string;
  year: number | null;
  description: string;
  genre: string;
  source: string;
  language: string;
  excerpt: string;
  highlights: string[];
  status: "empty" | "queued" | "processing" | "ready" | "failed";
  visible: boolean;
  window: number;
  extractor: string;
  error: string | null;
  n_documents: number;
  n_chunks: number;
  n_entities: number;
  n_edges: number;
  n_mentions: number;
  created_at: string;
  updated_at: string;
  processed_at: string | null;
}

export interface EntityOut {
  id: number;
  text: string;
  label: string;
  count: number;
  degree: number;
  strength: number;
}

export interface CorpusDetail extends CorpusSummary {
  label_counts: Record<string, number>;
  top_entities: EntityOut[];
  max_weight: number;
  max_strength: number;
}

export interface DocumentOut {
  id: number;
  position: number;
  title: string;
  n_chunks: number;
  n_chars: number;
}

export interface MentionOut {
  entity_id: number;
  label: string;
  start: number;
  end: number;
}

export interface ChunkOut {
  id: number;
  document_id: number;
  document_title: string;
  position: number;
  text: string;
  mentions: MentionOut[];
}

export interface ChunkPage {
  items: ChunkOut[];
  total: number;
  page: number;
  page_size: number;
}

export interface GraphNode {
  id: number;
  text: string;
  label: string;
  count: number;
  degree: number;
  strength: number;
}

export interface GraphEdge {
  source: number;
  target: number;
  weight: number;
  count: number;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_nodes: number;
  total_edges: number;
  min_weight: number;
  max_weight: number;
  max_strength: number;
}

export interface NeighborOut {
  entity: EntityOut;
  weight: number;
  count: number;
}

export interface EntityDetail extends EntityOut {
  n_chunks: number;
  neighbors: NeighborOut[];
}

export interface EdgeDetail {
  source: EntityOut;
  target: EntityOut;
  weight: number;
  count: number;
  chunks: ChunkOut[];
}

export interface SearchHit {
  chunk: ChunkOut;
  snippet: string;
  score: number;
}

export interface SearchResponse {
  query: string;
  hits: SearchHit[];
  total: number;
}

export interface JobOut {
  id: number;
  corpus_id: number;
  corpus_slug: string;
  kind: string;
  status: "queued" | "running" | "done" | "failed";
  progress: number;
  message: string;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface HealthOut {
  status: string;
  version: string;
  extractor: string;
  admin_enabled: boolean;
  fts: boolean;
}
