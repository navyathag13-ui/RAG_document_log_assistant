/**
 * API client — typed fetch wrapper for all FastAPI backend endpoints.
 *
 * v2 adds: prompts, compare, evaluate, experiments, benchmark.
 * All v1 calls are preserved unchanged.
 */
import type {
  AskResponse,
  BenchmarkRunResponse,
  CompareResponse,
  DeleteResponse,
  DocumentsResponse,
  ExperimentStats,
  ExperimentsListResponse,
  HealthResponse,
  IngestResponse,
  PromptTemplate,
  PromptTemplatesResponse,
  SearchResponse,
} from '../types';

const BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  'http://127.0.0.1:8000';

/** Generic fetch wrapper — throws a typed Error on non-2xx responses. */
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, options);
  } catch {
    throw new Error(
      'Cannot reach the backend. Is the FastAPI server running on ' + BASE_URL + '?'
    );
  }

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = (body as { detail?: string } | null)?.detail;
    throw new Error(detail ?? `Request failed: HTTP ${res.status}`);
  }

  // 204 No Content → return undefined cast to T
  if (res.status === 204) return undefined as T;

  return res.json() as Promise<T>;
}

// ── v1 endpoints (unchanged) ───────────────────────────────────────────────────

export const api = {
  // ── Health ────────────────────────────────────────────────────────────────
  getHealth(): Promise<HealthResponse> {
    return request<HealthResponse>('/health');
  },

  // ── Ingest ────────────────────────────────────────────────────────────────
  ingestFile(file: File): Promise<IngestResponse> {
    const formData = new FormData();
    formData.append('file', file);
    return request<IngestResponse>('/ingest', { method: 'POST', body: formData });
  },

  // ── Documents ─────────────────────────────────────────────────────────────
  getDocuments(): Promise<DocumentsResponse> {
    return request<DocumentsResponse>('/documents');
  },

  deleteDocument(docId: string): Promise<DeleteResponse> {
    return request<DeleteResponse>(`/documents/${encodeURIComponent(docId)}`, {
      method: 'DELETE',
    });
  },

  // ── Search ────────────────────────────────────────────────────────────────
  search(
    query: string,
    topK: number,
    useHybrid = false,
    hybridAlpha = 0.7
  ): Promise<SearchResponse> {
    return request<SearchResponse>('/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        top_k: topK,
        use_hybrid: useHybrid,
        hybrid_alpha: hybridAlpha,
      }),
    });
  },

  // ── Ask ───────────────────────────────────────────────────────────────────
  ask(
    question: string,
    topK: number,
    templateId?: string,
    autoEvaluate = true
  ): Promise<AskResponse> {
    return request<AskResponse>('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        top_k: topK,
        template_id: templateId ?? null,
        auto_evaluate: autoEvaluate,
      }),
    });
  },

  // ── v2: Prompt templates ─────────────────────────────────────────────────
  getPrompts(): Promise<PromptTemplatesResponse> {
    return request<PromptTemplatesResponse>('/prompts');
  },

  createPrompt(
    name: string,
    description: string,
    systemPrompt: string
  ): Promise<PromptTemplate> {
    return request<PromptTemplate>('/prompts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description, system_prompt: systemPrompt }),
    });
  },

  deletePrompt(templateId: string): Promise<void> {
    return request<void>(`/prompts/${encodeURIComponent(templateId)}`, {
      method: 'DELETE',
    });
  },

  // ── v2: Comparison ────────────────────────────────────────────────────────
  comparePrompts(
    question: string,
    topK: number,
    templateIds: string[]
  ): Promise<CompareResponse> {
    return request<CompareResponse>('/compare', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, top_k: topK, template_ids: templateIds }),
    });
  },

  // ── v2: Experiments ───────────────────────────────────────────────────────
  getExperiments(
    limit = 50,
    offset = 0,
    runType?: string
  ): Promise<ExperimentsListResponse> {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (runType) params.set('run_type', runType);
    return request<ExperimentsListResponse>(`/experiments?${params}`);
  },

  getExperimentStats(): Promise<ExperimentStats> {
    return request<ExperimentStats>('/experiments/stats');
  },

  deleteExperiment(runId: string): Promise<void> {
    return request<void>(`/experiments/${encodeURIComponent(runId)}`, {
      method: 'DELETE',
    });
  },

  // ── v2: Benchmark ─────────────────────────────────────────────────────────
  runBenchmark(templateId: string, topK: number): Promise<BenchmarkRunResponse> {
    return request<BenchmarkRunResponse>('/benchmark/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ template_id: templateId, top_k: topK }),
    });
  },
};
