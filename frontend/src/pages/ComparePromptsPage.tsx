/**
 * ComparePromptsPage — run the same question through up to 4 prompt templates
 * and view evaluation scores side-by-side.
 *
 * This page demonstrates:
 *   - Prompt engineering: how system prompt wording changes answer style/quality
 *   - Systematic evaluation: groundedness, relevance, completeness, clarity, hallucination risk
 *   - Experiment tracking: every comparison is persisted for historical review
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  GitCompare,
  Send,
  Upload,
  ChevronDown,
  ChevronUp,
  Trophy,
  Brain,
  Zap,
} from 'lucide-react'
import { api } from '../api/client'
import type { CompareResponse, CompareItem, PromptTemplate } from '../types'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Spinner from '../components/ui/Spinner'
import EvalScoreCard from '../components/ui/EvalScoreCard'
import ScoreBar from '../components/ui/ScoreBar'

const EXAMPLE_QUESTIONS = [
  'What should I check if the hydraulic pump overheats?',
  'What are the restart steps after a sensor communication fault?',
  'Summarise the troubleshooting steps for a pressure drop alert.',
  'What voltage range is required for the EDC electronics?',
  'What caused the FAULT-T02 overtemperature incident?',
]

const TOP_K_OPTIONS = [3, 5, 8]

// ── Single comparison panel ───────────────────────────────────────────────────

function ComparisonPanel({
  item,
  rank,
  isBest,
}: {
  item: CompareItem
  rank: number
  isBest: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const [sourcesOpen, setSourcesOpen] = useState(false)

  return (
    <div className={`flex flex-col rounded-xl border shadow-sm overflow-hidden ${
      isBest ? 'border-emerald-400 ring-2 ring-emerald-100' : 'border-slate-200'
    }`}>
      {/* Template header */}
      <div className={`px-4 py-3 flex items-center justify-between gap-2 ${
        isBest ? 'bg-emerald-50 border-b border-emerald-200' : 'bg-slate-50 border-b border-slate-200'
      }`}>
        <div className="flex items-center gap-2 min-w-0">
          <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
            isBest ? 'bg-emerald-500 text-white' : 'bg-slate-200 text-slate-600'
          }`}>
            {rank}
          </div>
          <span className="text-sm font-bold text-slate-800 truncate">{item.template_name}</span>
          {isBest && (
            <span className="flex items-center gap-1 text-xs text-emerald-700 font-semibold shrink-0">
              <Trophy size={11} /> Best
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {item.llm_used ? (
            <span className="flex items-center gap-1 text-xs text-blue-600">
              <Brain size={11} /> LLM
            </span>
          ) : (
            <span className="flex items-center gap-1 text-xs text-amber-600">
              <Zap size={11} /> Fallback
            </span>
          )}
          <span className="text-xs font-bold text-slate-700 bg-white border border-slate-200 rounded-full px-2 py-0.5">
            {Math.round(item.overall_score * 100)}
          </span>
        </div>
      </div>

      {/* Answer text */}
      <div className="p-4 flex-1">
        <p className={`text-sm text-slate-700 leading-relaxed whitespace-pre-wrap ${
          expanded ? '' : 'line-clamp-5'
        }`}>
          {item.answer}
        </p>
        {item.answer.length > 300 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="mt-2 flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium"
          >
            {expanded ? <><ChevronUp size={10} /> Less</> : <><ChevronDown size={10} /> Full answer</>}
          </button>
        )}
      </div>

      {/* Eval scores */}
      <div className="px-4 pb-3">
        <EvalScoreCard
          scores={{
            groundedness_score: item.groundedness_score,
            relevance_score: item.relevance_score,
            completeness_score: item.completeness_score,
            clarity_score: item.clarity_score,
            hallucination_risk: item.hallucination_risk,
            overall_score: item.overall_score,
          }}
        />
      </div>

      {/* Sources toggle */}
      {item.sources.length > 0 && (
        <div className="px-4 pb-4">
          <button
            onClick={() => setSourcesOpen(!sourcesOpen)}
            className="w-full text-left text-xs text-slate-500 hover:text-slate-700 font-medium flex items-center gap-1"
          >
            {sourcesOpen ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
            {item.sources.length} source{item.sources.length !== 1 ? 's' : ''} retrieved
          </button>
          {sourcesOpen && (
            <div className="mt-2 space-y-2">
              {item.sources.map((s, i) => (
                <div key={s.chunk_id} className="bg-slate-50 rounded-lg p-2.5 border border-slate-100">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs text-slate-400 font-mono">#{i + 1}</span>
                    <Badge variant="filetype" fileType={s.file_type}>{s.file_type.toUpperCase()}</Badge>
                    <span className="text-xs font-medium text-slate-700 truncate">{s.doc_name}</span>
                    <span className="ml-auto"><ScoreBar score={s.score} compact /></span>
                  </div>
                  <p className="text-xs text-slate-500 leading-relaxed line-clamp-2">{s.text_excerpt}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Summary comparison table ──────────────────────────────────────────────────

function ComparisonTable({ comparisons }: { comparisons: CompareItem[] }) {
  const dims = [
    { key: 'overall_score',       label: 'Overall'       },
    { key: 'groundedness_score',  label: 'Grounded'      },
    { key: 'relevance_score',     label: 'Relevance'     },
    { key: 'completeness_score',  label: 'Complete'      },
    { key: 'clarity_score',       label: 'Clarity'       },
    { key: 'hallucination_risk',  label: 'Halluc. Risk'  },
  ] as const

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr className="bg-slate-50">
            <th className="text-left p-2.5 font-semibold text-slate-600 border-b border-slate-200">
              Template
            </th>
            {dims.map((d) => (
              <th key={d.key} className="text-center p-2.5 font-semibold text-slate-600 border-b border-slate-200 whitespace-nowrap">
                {d.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {[...comparisons]
            .sort((a, b) => b.overall_score - a.overall_score)
            .map((item, i) => (
              <tr key={item.template_id} className={i % 2 === 0 ? 'bg-white' : 'bg-slate-50/50'}>
                <td className="p-2.5 font-medium text-slate-800 border-b border-slate-100">
                  {item.template_name}
                </td>
                {dims.map((d) => {
                  const val = item[d.key] as number
                  const pct = Math.round(val * 100)
                  const isRisk = d.key === 'hallucination_risk'
                  const good = isRisk ? pct < 20 : pct >= 70
                  const warn = isRisk ? pct >= 20 && pct < 50 : pct >= 45 && pct < 70
                  return (
                    <td key={d.key} className="p-2.5 text-center border-b border-slate-100">
                      <span className={`font-bold font-mono ${
                        good ? 'text-emerald-700' : warn ? 'text-amber-600' : 'text-red-600'
                      }`}>
                        {isRisk ? `${pct}%` : `${pct}%`}
                      </span>
                    </td>
                  )
                })}
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ComparePromptsPage() {
  const navigate = useNavigate()
  const [question, setQuestion] = useState('')
  const [topK, setTopK] = useState(5)
  const [selectedIds, setSelectedIds] = useState<string[]>(['technical', 'detailed', 'concise'])
  const [result, setResult] = useState<CompareResponse | null>(null)

  // Load available templates
  const { data: promptsData } = useQuery({
    queryKey: ['prompts'],
    queryFn: api.getPrompts,
  })

  const compareMutation = useMutation<
    CompareResponse,
    Error,
    { question: string; topK: number; templateIds: string[] }
  >({
    mutationFn: ({ question, topK, templateIds }) =>
      api.comparePrompts(question, topK, templateIds),
    onSuccess: (data) => setResult(data),
  })

  const toggleTemplate = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id)
        ? prev.filter((x) => x !== id)
        : prev.length < 4
        ? [...prev, id]
        : prev
    )
  }

  const handleRun = () => {
    const q = question.trim()
    if (!q || selectedIds.length === 0) return
    setResult(null)
    compareMutation.mutate({ question: q, topK, templateIds: selectedIds })
  }

  // Sort results by overall score descending
  const sorted = result
    ? [...result.comparisons].sort((a, b) => b.overall_score - a.overall_score)
    : []

  return (
    <div className="max-w-7xl mx-auto px-8 py-8">

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-1">
          <GitCompare size={20} className="text-violet-600" />
          <h1 className="text-2xl font-bold text-slate-900">Compare Prompt Templates</h1>
        </div>
        <p className="text-slate-500 text-sm">
          Run the same question through multiple prompt templates and compare answers, sources,
          and evaluation scores side-by-side. Results are saved to Experiment History.
        </p>
      </div>

      {/* ── Query card ──────────────────────────────────────────────────── */}
      <Card className="p-5 mb-6">

        {/* Question input */}
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Enter a question to compare across templates…"
          rows={3}
          className="w-full px-4 py-3 text-sm bg-slate-50 border border-slate-300 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent focus:bg-white transition-colors"
        />

        {/* Template selector */}
        <div className="mt-3">
          <p className="text-xs font-semibold text-slate-600 mb-2">
            Select templates to compare (1–4):
          </p>
          <div className="flex flex-wrap gap-2">
            {(promptsData?.templates ?? []).map((tmpl: PromptTemplate) => {
              const active = selectedIds.includes(tmpl.id)
              return (
                <button
                  key={tmpl.id}
                  onClick={() => toggleTemplate(tmpl.id)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                    active
                      ? 'bg-violet-600 text-white border-violet-600'
                      : 'bg-white text-slate-600 border-slate-300 hover:border-violet-400'
                  }`}
                >
                  {tmpl.name}
                  {tmpl.is_builtin ? '' : ' ★'}
                </button>
              )
            })}
          </div>
          {selectedIds.length === 0 && (
            <p className="text-xs text-red-500 mt-1">Select at least one template.</p>
          )}
        </div>

        {/* Controls row */}
        <div className="flex items-center justify-between mt-3 flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 font-medium">Sources per template:</span>
            {TOP_K_OPTIONS.map((n) => (
              <button
                key={n}
                onClick={() => setTopK(n)}
                className={`w-8 h-7 rounded-md text-xs font-semibold transition-colors ${
                  topK === n ? 'bg-violet-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {n}
              </button>
            ))}
          </div>
          <Button
            variant="primary"
            size="md"
            loading={compareMutation.isPending}
            iconRight={compareMutation.isPending ? undefined : <Send size={14} />}
            onClick={handleRun}
            disabled={!question.trim() || selectedIds.length === 0}
            className="bg-violet-600 hover:bg-violet-700 focus-visible:ring-violet-500"
          >
            {compareMutation.isPending ? 'Running…' : `Compare ${selectedIds.length} Template${selectedIds.length !== 1 ? 's' : ''}`}
          </Button>
        </div>

        {/* Example questions */}
        {!result && !compareMutation.isPending && (
          <div className="mt-3 pt-3 border-t border-slate-100">
            <p className="text-xs text-slate-400 mb-2">Try:</p>
            <div className="flex flex-wrap gap-1.5">
              {EXAMPLE_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => setQuestion(q)}
                  className="px-2.5 py-1 bg-slate-100 hover:bg-violet-50 hover:text-violet-700 text-slate-600 rounded-full text-xs transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
      </Card>

      {/* ── Loading ──────────────────────────────────────────────────────── */}
      {compareMutation.isPending && (
        <Card className="p-8 flex flex-col items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-violet-50 flex items-center justify-center">
            <Spinner size={22} className="text-violet-500" />
          </div>
          <div className="text-center">
            <p className="text-sm font-semibold text-slate-800">Running {selectedIds.length} templates…</p>
            <p className="text-xs text-slate-400 mt-1">
              Retrieving context · Generating {selectedIds.length} answers · Evaluating each
            </p>
          </div>
        </Card>
      )}

      {/* ── Error ────────────────────────────────────────────────────────── */}
      {compareMutation.isError && (
        <Card accent="red" className="p-5">
          <p className="text-sm font-medium text-red-700">Comparison failed</p>
          <p className="text-sm text-slate-500 mt-1">{compareMutation.error.message}</p>
          {compareMutation.error.message.includes('No documents') && (
            <Button
              variant="secondary"
              size="sm"
              className="mt-3"
              iconLeft={<Upload size={13} />}
              onClick={() => navigate('/upload')}
            >
              Upload documents first
            </Button>
          )}
        </Card>
      )}

      {/* ── Results ──────────────────────────────────────────────────────── */}
      {result && !compareMutation.isPending && (
        <div className="space-y-6">

          {/* Summary table */}
          <Card className="overflow-hidden">
            <div className="px-5 py-3 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
              <span className="text-sm font-semibold text-slate-700">Score Summary</span>
              <span className="text-xs text-slate-400">
                {result.comparisons.length} templates · {result.top_k} sources each
              </span>
            </div>
            <ComparisonTable comparisons={result.comparisons} />
          </Card>

          {/* Side-by-side panels */}
          <div
            className={`grid gap-4 ${
              sorted.length === 1
                ? 'grid-cols-1 max-w-xl'
                : sorted.length === 2
                ? 'grid-cols-1 md:grid-cols-2'
                : sorted.length === 3
                ? 'grid-cols-1 md:grid-cols-3'
                : 'grid-cols-1 md:grid-cols-2 xl:grid-cols-4'
            }`}
          >
            {sorted.map((item, i) => (
              <ComparisonPanel
                key={item.template_id}
                item={item}
                rank={i + 1}
                isBest={item.template_id === result.best_template_id}
              />
            ))}
          </div>

          <p className="text-xs text-slate-400 text-center">
            Results saved to{' '}
            <button
              onClick={() => navigate('/experiments')}
              className="text-blue-600 hover:underline"
            >
              Experiment History
            </button>
          </p>
        </div>
      )}
    </div>
  )
}
