/**
 * TypeScript types that mirror the FastAPI response schemas exactly.
 * v2 adds: PromptTemplate, CompareResponse, EvalScores, ExperimentRun, ExperimentStats,
 *          BenchmarkRunResponse, and enriched AskResponse / SearchResponse.
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
  retrieval_mode: string;   // "semantic" | "hybrid"
}

// ── Ask / QA ───────────────────────────────────────────────────────────────────
export interface SourceChunk {
  chunk_id: string;
  doc_name: string;
  file_type: string;
  text_excerpt: string;
  score: number;
}

export interface EvalScores {
  groundedness_score: number;
  relevance_score: number;
  completeness_score: number;
  clarity_score: number;
  hallucination_risk: number;
  overall_score: number;
  method: string;
}

export interface AskResponse {
  question: string;
  answer: string;
  llm_used: boolean;
  retrieval_count: number;
  sources: SourceChunk[];
  // v2 enrichments (optional — present when auto_evaluate=true)
  evaluation?: EvalScores | null;
  experiment_run_id?: string | null;
  template_name?: string | null;
}

// ── Delete ─────────────────────────────────────────────────────────────────────
export interface DeleteResponse {
  message: string;
  doc_id: string;
  chunks_deleted: number;
}

// ══════════════════════════════════════════════════════════════════════════════
// v2 types
// ══════════════════════════════════════════════════════════════════════════════

// ── Prompt templates ──────────────────────────────────────────────────────────
export interface PromptTemplate {
  id: string;
  name: string;
  description: string | null;
  system_prompt: string;
  is_builtin: number;   // 1 = built-in, 0 = custom
  created_at: string;
  updated_at: string;
}

export interface PromptTemplatesResponse {
  total: number;
  templates: PromptTemplate[];
}

// ── Comparison ────────────────────────────────────────────────────────────────
export interface CompareItem {
  template_id: string;
  template_name: string;
  answer: string;
  llm_used: boolean;
  retrieval_count: number;
  sources: SourceChunk[];
  groundedness_score: number;
  relevance_score: number;
  completeness_score: number;
  clarity_score: number;
  hallucination_risk: number;
  overall_score: number;
  experiment_run_id: string;
}

export interface CompareResponse {
  question: string;
  top_k: number;
  comparisons: CompareItem[];
  best_template_id: string | null;
}

// ── Experiments ───────────────────────────────────────────────────────────────
export interface ExperimentRun {
  id: string;
  query: string;
  prompt_template_id: string | null;
  prompt_template_name: string | null;
  top_k: number;
  answer: string;
  llm_used: number;   // 0 | 1
  retrieval_count: number;
  run_type: string;
  created_at: string;
  // Joined evaluation fields
  groundedness_score: number | null;
  relevance_score: number | null;
  completeness_score: number | null;
  clarity_score: number | null;
  hallucination_risk: number | null;
  overall_score: number | null;
  eval_method: string | null;
}

export interface ExperimentsListResponse {
  total: number;
  runs: ExperimentRun[];
}

export interface TemplateLeaderboardEntry {
  template_name: string;
  run_count: number;
  avg_score: number | null;
  avg_groundedness: number | null;
  avg_relevance: number | null;
}

export interface ExperimentStats {
  total_runs: number;
  avg_overall_score: number;
  avg_groundedness: number;
  avg_relevance: number;
  avg_completeness: number;
  avg_clarity: number;
  avg_hallucination_risk: number;
  by_template: TemplateLeaderboardEntry[];
}

// ── Benchmark ─────────────────────────────────────────────────────────────────
export interface BenchmarkQuestionResult {
  question_id: string;
  question: string;
  category: string;
  difficulty: string;
  answer: string;
  overall_score: number;
  groundedness_score: number;
  relevance_score: number;
  experiment_run_id: string;
}

export interface BenchmarkRunResponse {
  template_id: string;
  template_name: string;
  top_k: number;
  total_questions: number;
  avg_overall_score: number;
  results: BenchmarkQuestionResult[];
}

// ══════════════════════════════════════════════════════════════════════════════
// Shared helpers
// ══════════════════════════════════════════════════════════════════════════════

export type SupportedFileType = 'txt' | 'md' | 'log' | 'pdf';

/** Visual config for each file type. */
export const FILE_TYPE_CONFIG: Record<
  string,
  { bg: string; text: string; border: string; label: string }
> = {
  txt: { bg: 'bg-slate-100',  text: 'text-slate-700',  border: 'border-slate-200',  label: 'TXT' },
  md:  { bg: 'bg-blue-50',    text: 'text-blue-700',    border: 'border-blue-100',    label: 'MD'  },
  log: { bg: 'bg-amber-50',   text: 'text-amber-700',   border: 'border-amber-100',   label: 'LOG' },
  pdf: { bg: 'bg-red-50',     text: 'text-red-700',     border: 'border-red-100',     label: 'PDF' },
};

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

export function formatDate(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Intl.DateTimeFormat('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}
