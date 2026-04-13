/**
 * API client — thin wrapper around fetch that targets the FastAPI backend.
 *
 * All request shapes match the backend's Pydantic schemas exactly.
 * The base URL is read from the VITE_API_BASE_URL environment variable so the
 * same build can point at different environments without code changes.
 */
import type {
  AskResponse,
  DeleteResponse,
  DocumentsResponse,
  HealthResponse,
  IngestResponse,
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
      'Cannot reach the backend. Is the FastAPI server running on ' +
        BASE_URL +
        '?'
    );
  }

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = (body as { detail?: string } | null)?.detail;
    throw new Error(detail ?? `Request failed: HTTP ${res.status}`);
  }

  return res.json() as Promise<T>;
}

// ── Public API surface ─────────────────────────────────────────────────────────

export const api = {
  /** GET /health */
  getHealth(): Promise<HealthResponse> {
    return request<HealthResponse>('/health');
  },

  /**
   * POST /ingest  (multipart/form-data)
   * We do NOT set Content-Type — the browser adds the correct
   * multipart boundary automatically when given a FormData body.
   */
  ingestFile(file: File): Promise<IngestResponse> {
    const formData = new FormData();
    formData.append('file', file);
    return request<IngestResponse>('/ingest', {
      method: 'POST',
      body: formData,
    });
  },

  /** GET /documents */
  getDocuments(): Promise<DocumentsResponse> {
    return request<DocumentsResponse>('/documents');
  },

  /** POST /search */
  search(query: string, topK: number): Promise<SearchResponse> {
    return request<SearchResponse>('/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, top_k: topK }),
    });
  },

  /** POST /ask */
  ask(question: string, topK: number): Promise<AskResponse> {
    return request<AskResponse>('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, top_k: topK }),
    });
  },

  /** DELETE /documents/{doc_id} */
  deleteDocument(docId: string): Promise<DeleteResponse> {
    return request<DeleteResponse>(
      `/documents/${encodeURIComponent(docId)}`,
      { method: 'DELETE' }
    );
  },
};
