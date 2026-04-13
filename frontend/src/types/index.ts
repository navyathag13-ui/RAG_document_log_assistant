/**
 * TypeScript types that mirror the FastAPI response schemas exactly.
 * Changing these without also changing the backend will cause runtime errors.
 */

// ── Health ─────────────────────────────────────────────────────────────────────
export interface HealthResponse {
  status: string;
  version: string;
  indexed_documents: number;
  total_chunks: number;
  llm_available: boolean;
}

// ── Ingest ─────────────────────────────────────────────────────────────────────
export interface IngestResponse {
  message: string;
  doc_id: string;
  file_type: string;
  chunks_created: number;
}

// ── Documents ──────────────────────────────────────────────────────────────────
export interface DocumentInfo {
  doc_id: string;
  file_type: string;
  chunks: number;
  ingested_at: string | null;
  source_path: string | null;
}

export interface DocumentsResponse {
  total_documents: number;
  total_chunks: number;
  documents: DocumentInfo[];
}

// ── Search ─────────────────────────────────────────────────────────────────────
export interface ChunkResult {
  chunk_id: string;
  text: string;
  score: number;
  doc_name: string;
  file_type: string;
  chunk_index: number;
  source_path: string | null;
}

export interface SearchResponse {
  query: string;
  results: ChunkResult[];
  total_results: number;
}

// ── Ask / QA ───────────────────────────────────────────────────────────────────
export interface SourceChunk {
  chunk_id: string;
  doc_name: string;
  file_type: string;
  text_excerpt: string;
  score: number;
}

export interface AskResponse {
  question: string;
  answer: string;
  llm_used: boolean;
  retrieval_count: number;
  sources: SourceChunk[];
}

// ── Delete ─────────────────────────────────────────────────────────────────────
export interface DeleteResponse {
  message: string;
  doc_id: string;
  chunks_deleted: number;
}

// ── Shared helpers ─────────────────────────────────────────────────────────────
export type SupportedFileType = 'txt' | 'md' | 'log' | 'pdf';

/** Visual config for each file type — colors and labels. */
export const FILE_TYPE_CONFIG: Record<
  string,
  { bg: string; text: string; border: string; label: string }
> = {
  txt: {
    bg: 'bg-slate-100',
    text: 'text-slate-700',
    border: 'border-slate-200',
    label: 'TXT',
  },
  md: {
    bg: 'bg-blue-50',
    text: 'text-blue-700',
    border: 'border-blue-100',
    label: 'MD',
  },
  log: {
    bg: 'bg-amber-50',
    text: 'text-amber-700',
    border: 'border-amber-100',
    label: 'LOG',
  },
  pdf: {
    bg: 'bg-red-50',
    text: 'text-red-700',
    border: 'border-red-100',
    label: 'PDF',
  },
};

/** Score → color class mapping for similarity score visualisation. */
export function scoreColor(score: number): string {
  if (score >= 0.75) return 'text-emerald-600';
  if (score >= 0.55) return 'text-blue-600';
  if (score >= 0.35) return 'text-amber-600';
  return 'text-slate-500';
}

export function scoreBarColor(score: number): string {
  if (score >= 0.75) return 'bg-emerald-500';
  if (score >= 0.55) return 'bg-blue-500';
  if (score >= 0.35) return 'bg-amber-500';
  return 'bg-slate-400';
}

export function scoreLabel(score: number): string {
  if (score >= 0.75) return 'High';
  if (score >= 0.55) return 'Good';
  if (score >= 0.35) return 'Medium';
  return 'Low';
}

/** Format an ISO timestamp into a human-friendly string. */
export function formatDate(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}
