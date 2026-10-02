import { useEffect } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  api,
  query,
  type ChunkPage,
  type ContactMessage,
  type CorpusDetail,
  type CorpusSummary,
  type DocumentOut,
  type EdgeDetail,
  type EntityDetail,
  type EntityOut,
  type GraphResponse,
  type HealthOut,
  type IndexResponse,
  type JobOut,
  type PageOut,
  type PageRefList,
  type SearchResponse,
} from "@/lib/api";

export const keys = {
  health: ["health"] as const,
  corpora: (all: boolean) => ["corpora", all] as const,
  corpus: (slug: string) => ["corpus", slug] as const,
  documents: (slug: string) => ["documents", slug] as const,
  graph: (slug: string, params: GraphParams) => ["graph", slug, params] as const,
  chunks: (slug: string, params: ChunkParams) => ["chunks", slug, params] as const,
  search: (slug: string, q: string, entityIds: number[]) => ["search", slug, q, entityIds] as const,
  entity: (slug: string, id: number | null, k: number) => ["entity", slug, id, k] as const,
  entities: (slug: string, q: string) => ["entities", slug, q] as const,
  edge: (slug: string, a: number | null, b: number | null) => ["edge", slug, a, b] as const,
  page: (slug: string, number: number) => ["page", slug, number] as const,
  pageGraph: (slug: string, number: number) => ["page-graph", slug, number] as const,
  pageRefs: (slug: string, params: PageRefParams) => ["page-refs", slug, params] as const,
  index: (slug: string) => ["index", slug] as const,
  jobs: ["jobs"] as const,
  job: (id: number | null) => ["job", id] as const,
};

export interface GraphParams {
  min_weight: number;
  max_nodes: number;
  labels: string[];
  focus: number | null;
}

export interface PageRefParams {
  entity_id: number[];
  document_id: number | null;
  limit?: number;
}

export interface ChunkParams {
  document_id: number | null;
  entity_id: number[];
  page: number;
  page_size: number;
}

export function useHealth() {
  return useQuery({ queryKey: keys.health, queryFn: () => api<HealthOut>("/api/health"), staleTime: 60_000 });
}

export function useCorpora(all = false) {
  return useQuery({ queryKey: keys.corpora(all), queryFn: () => api<CorpusSummary[]>(`/api/corpora${query({ all: all || undefined })}`) });
}

export function useCorpus(slug: string) {
  return useQuery({ queryKey: keys.corpus(slug), queryFn: () => api<CorpusDetail>(`/api/corpora/${slug}`) });
}

export function useDocuments(slug: string) {
  return useQuery({ queryKey: keys.documents(slug), queryFn: () => api<DocumentOut[]>(`/api/corpora/${slug}/documents`), staleTime: 5 * 60_000 });
}

export function useGraph(slug: string, params: GraphParams, enabled = true) {
  return useQuery({
    queryKey: keys.graph(slug, params),
    queryFn: () => api<GraphResponse>(`/api/corpora/${slug}/graph${query({ ...params, focus: params.focus ?? undefined })}`),
    placeholderData: keepPreviousData,
    enabled,
    staleTime: 5 * 60_000,
  });
}

export function useChunks(slug: string, params: ChunkParams, enabled = true) {
  return useQuery({
    queryKey: keys.chunks(slug, params),
    queryFn: () => api<ChunkPage>(`/api/corpora/${slug}/chunks${query({ ...params, document_id: params.document_id ?? undefined })}`),
    placeholderData: keepPreviousData,
    enabled,
  });
}

export function useSearch(slug: string, q: string, entityIds: number[], limit = 30) {
  return useQuery({
    queryKey: keys.search(slug, q, entityIds),
    queryFn: () => api<SearchResponse>(`/api/corpora/${slug}/search${query({ q, entity_id: entityIds, limit })}`),
    enabled: q.trim().length > 0,
    placeholderData: keepPreviousData,
  });
}

export function useEntity(slug: string, id: number | null, k = 25) {
  return useQuery({
    queryKey: keys.entity(slug, id, k),
    queryFn: () => api<EntityDetail>(`/api/corpora/${slug}/entities/${id}${query({ k })}`),
    enabled: id !== null,
    staleTime: 10 * 60_000,
  });
}

export function useEntitySearch(slug: string, q: string) {
  return useQuery({
    queryKey: keys.entities(slug, q),
    queryFn: () => api<EntityOut[]>(`/api/corpora/${slug}/entities${query({ q, limit: 8 })}`),
    enabled: q.trim().length > 0,
    placeholderData: keepPreviousData,
  });
}

export function useEdge(slug: string, a: number | null, b: number | null) {
  return useQuery({ queryKey: keys.edge(slug, a, b), queryFn: () => api<EdgeDetail>(`/api/corpora/${slug}/edges/${a}/${b}`), enabled: a !== null && b !== null });
}

// ---------------------------------------------------------------- pages

export function usePage(slug: string, number: number, enabled = true) {
  return useQuery({
    queryKey: keys.page(slug, number),
    queryFn: () => api<PageOut>(`/api/corpora/${slug}/pages/${number}`),
    placeholderData: keepPreviousData,
    enabled: enabled && number >= 1,
    staleTime: 10 * 60_000,
  });
}

/** Warm the cache for the pages next to the current one so turning a page feels instant. */
export function usePrefetchPages(slug: string, number: number, nPages: number) {
  const client = useQueryClient();
  useEffect(() => {
    for (const next of [number + 1, number - 1]) {
      if (next < 1 || next > nPages) continue;
      client.prefetchQuery({
        queryKey: keys.page(slug, next),
        queryFn: () => api<PageOut>(`/api/corpora/${slug}/pages/${next}`),
        staleTime: 10 * 60_000,
      });
    }
  }, [client, slug, number, nPages]);
}

export function usePageGraph(slug: string, number: number, enabled = true) {
  return useQuery({
    queryKey: keys.pageGraph(slug, number),
    queryFn: () => api<GraphResponse>(`/api/corpora/${slug}/pages/${number}/graph`),
    placeholderData: keepPreviousData,
    enabled: enabled && number >= 1,
    staleTime: 10 * 60_000,
  });
}

export function usePageRefs(slug: string, params: PageRefParams, enabled = true) {
  return useQuery({
    queryKey: keys.pageRefs(slug, params),
    queryFn: () =>
      api<PageRefList>(`/api/corpora/${slug}/pages${query({ ...params, document_id: params.document_id ?? undefined, limit: params.limit ?? 2000 })}`),
    placeholderData: keepPreviousData,
    enabled,
    staleTime: 10 * 60_000,
  });
}

export function useIndex(slug: string, enabled = true) {
  return useQuery({
    queryKey: keys.index(slug),
    queryFn: () => api<IndexResponse>(`/api/corpora/${slug}/index`),
    enabled,
    staleTime: 10 * 60_000,
  });
}

// ---------------------------------------------------------------- admin

export function useJobs(enabled: boolean) {
  return useQuery({
    queryKey: keys.jobs,
    queryFn: () => api<JobOut[]>("/api/admin/jobs"),
    enabled,
    refetchInterval: (q) => (q.state.data?.some((j) => j.status === "queued" || j.status === "running") ? 1500 : false),
  });
}

export function useJob(id: number | null) {
  return useQuery({
    queryKey: keys.job(id),
    queryFn: () => api<JobOut>(`/api/admin/jobs/${id}`),
    enabled: id !== null,
    refetchInterval: (q) => (q.state.data && (q.state.data.status === "queued" || q.state.data.status === "running") ? 1200 : false),
  });
}

export function useSendMessage() {
  return useMutation({
    mutationFn: (body: { name: string; email: string; message: string; website: string }) => api<{ status: string }>("/api/contact", { method: "POST", body }),
  });
}

export function useMessages(enabled: boolean) {
  return useQuery({ queryKey: ["messages"], queryFn: () => api<ContactMessage[]>("/api/admin/messages"), enabled });
}

export function useMessageMutations() {
  const client = useQueryClient();
  const invalidate = () => client.invalidateQueries({ queryKey: ["messages"] });
  const markHandled = useMutation({
    mutationFn: ({ id, handled }: { id: number; handled: boolean }) => api<ContactMessage>(`/api/admin/messages/${id}`, { method: "PATCH", body: { handled } }),
    onSuccess: invalidate,
  });
  const deleteMessage = useMutation({
    mutationFn: (id: number) => api<void>(`/api/admin/messages/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });
  return { markHandled, deleteMessage };
}

export function useAdminMutations() {
  const client = useQueryClient();
  const invalidate = () => {
    client.invalidateQueries({ queryKey: ["corpora"] });
    client.invalidateQueries({ queryKey: ["corpus"] });
    client.invalidateQueries({ queryKey: keys.jobs });
  };
  const createCorpus = useMutation({
    mutationFn: (body: Record<string, unknown>) => api<CorpusSummary>("/api/admin/corpora", { method: "POST", body }),
    onSuccess: invalidate,
  });
  const uploadCorpus = useMutation({
    mutationFn: (form: FormData) => api<CorpusSummary>("/api/admin/corpora/upload", { method: "POST", form }),
    onSuccess: invalidate,
  });
  const processCorpus = useMutation({
    mutationFn: (slug: string) => api<JobOut>(`/api/admin/corpora/${slug}/process`, { method: "POST" }),
    onSuccess: invalidate,
  });
  const updateCorpus = useMutation({
    mutationFn: ({ slug, body }: { slug: string; body: Record<string, unknown> }) => api<CorpusSummary>(`/api/admin/corpora/${slug}`, { method: "PATCH", body }),
    onSuccess: invalidate,
  });
  const deleteCorpus = useMutation({
    mutationFn: (slug: string) => api<void>(`/api/admin/corpora/${slug}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });
  return { createCorpus, uploadCorpus, processCorpus, updateCorpus, deleteCorpus };
}
