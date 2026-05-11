/**
 * ExperimentsPage — full experiment history with filters and expandable rows.
 *
 * Shows every /ask and /compare run with their evaluation scores.
 * Supports filtering by run type and deleting individual runs.
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  History,
  Brain,
  Zap,
  ChevronDown,
  ChevronUp,
  Trash2,
  RefreshCw,
  Filter,
} from 'lucide-react'
import { api } from '../api/client'
import type { ExperimentRun } from '../types'
import { formatDate } from '../types'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Spinner from '../components/ui/Spinner'
import EmptyState from '../components/ui/EmptyState'
import ConfirmDialog from '../components/ui/ConfirmDialog'

const RUN_TYPE_LABELS: Record<string, string> = {
  single:    'Ask',
  compare:   'Compare',
  benchmark: 'Benchmark',
}

const RUN_TYPE_COLORS: Record<string, string> = {
  single:    'info',
  compare:   'default',
  benchmark: 'success',
}

// ── Mini score pill ────────────────────────────────────────────────────────────

function ScorePill({ value, dim }: { value: number | null | undefined; dim: string }) {
  if (value == null) return <span className="text-xs text-slate-300">—</span>
  const pct = Math.round(value * 100)
  const color =
    pct >= 75 ? 'bg-emerald-100 text-emerald-700'
    : pct >= 50 ? 'bg-blue-100 text-blue-700'
    : pct >= 30 ? 'bg-amber-100 text-amber-700'
    : 'bg-red-100 text-red-600'

  return (
    <div className="text-center">
      <span className={`inline-block px-1.5 py-0.5 rounded text-xs font-bold font-mono ${color}`}>
        {pct}
      </span>
      <p className="text-xs text-slate-400 mt-0.5">{dim}</p>
    </div>
  )
}

// ── Expandable run row ─────────────────────────────────────────────────────────

function RunRow({ run, onDelete }: { run: ExperimentRun; onDelete: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)

  return (
    <>
      <div className="border border-slate-200 rounded-xl overflow-hidden mb-2">
        {/* Summary row */}
        <button
          className="w-full text-left p-4 hover:bg-slate-50 transition-colors"
          onClick={() => setExpanded(!expanded)}
        >
          <div className="flex items-start gap-3 flex-wrap">
            {/* Run type badge */}
            <Badge variant={RUN_TYPE_COLORS[run.run_type] as 'info' | 'default' | 'success'}>
              {RUN_TYPE_LABELS[run.run_type] ?? run.run_type}
            </Badge>

            {/* Query */}
            <p className="flex-1 text-sm text-slate-800 font-medium text-left line-clamp-1 min-w-0">
              {run.query}
            </p>

            {/* Meta */}
            <div className="flex items-center gap-3 shrink-0 flex-wrap">
              {run.prompt_template_name && (
                <span className="text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
                  {run.prompt_template_name}
                </span>
              )}
              {run.llm_used ? (
                <span className="flex items-center gap-1 text-xs text-blue-600">
                  <Brain size={10} /> LLM
                </span>
              ) : (
                <span className="flex items-center gap-1 text-xs text-amber-600">
                  <Zap size={10} /> Fallback
                </span>
              )}
              {run.overall_score != null && (
                <span className={`text-xs font-bold font-mono ${
                  run.overall_score >= 0.75 ? 'text-emerald-700'
                  : run.overall_score >= 0.5 ? 'text-blue-700'
                  : 'text-amber-600'
                }`}>
                  {Math.round(run.overall_score * 100)} / 100
                </span>
              )}
              <span className="text-xs text-slate-400">{formatDate(run.created_at)}</span>
              {expanded ? <ChevronUp size={14} className="text-slate-400" /> : <ChevronDown size={14} className="text-slate-400" />}
            </div>
          </div>
        </button>

        {/* Expanded detail */}
        {expanded && (
          <div className="border-t border-slate-100 p-4 bg-slate-50/60">
            {/* Scores */}
            {run.overall_score != null && (
              <div className="grid grid-cols-5 gap-3 mb-4 bg-white border border-slate-100 rounded-xl p-3">
                <ScorePill value={run.groundedness_score}  dim="Ground."  />
                <ScorePill value={run.relevance_score}     dim="Relev."   />
                <ScorePill value={run.completeness_score}  dim="Complete" />
                <ScorePill value={run.clarity_score}       dim="Clarity"  />
                <ScorePill value={run.hallucination_risk}  dim="Risk"     />
              </div>
            )}

            {/* Answer */}
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Answer</p>
            <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap bg-white border border-slate-100 rounded-xl p-4 max-h-48 overflow-y-auto">
              {run.answer}
            </p>

            {/* Meta */}
            <div className="flex items-center justify-between mt-3 flex-wrap gap-2">
              <span className="text-xs text-slate-400 font-mono">{run.id}</span>
              <Button
                variant="danger"
                size="sm"
                iconLeft={<Trash2 size={12} />}
                onClick={(e) => { e.stopPropagation(); setShowConfirm(true) }}
              >
                Delete
              </Button>
            </div>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={showConfirm}
        title="Delete experiment run?"
        description="This will permanently remove this run and its evaluation scores."
        onConfirm={() => { onDelete(run.id); setShowConfirm(false) }}
        onCancel={() => setShowConfirm(false)}
      />
    </>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ExperimentsPage() {
  const queryClient = useQueryClient()
  const [runTypeFilter, setRunTypeFilter] = useState<string>('all')

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['experiments', 'list', runTypeFilter],
    queryFn: () => api.getExperiments(50, 0, runTypeFilter === 'all' ? undefined : runTypeFilter),
  })

  const deleteMutation = useMutation<void, Error, string>({
    mutationFn: (id) => api.deleteExperiment(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['experiments'] })
    },
  })

  const runs: ExperimentRun[] = data?.runs ?? []

  const filters = [
    { key: 'all',       label: 'All'       },
    { key: 'single',    label: 'Ask'       },
    { key: 'compare',   label: 'Compare'   },
    { key: 'benchmark', label: 'Benchmark' },
  ]

  return (
    <div className="max-w-4xl mx-auto px-8 py-8">

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-1">
          <History size={20} className="text-slate-600" />
          <h1 className="text-2xl font-bold text-slate-900">Experiment History</h1>
        </div>
        <p className="text-slate-500 text-sm">
          All Ask, Compare, and Benchmark runs with their evaluation scores.
          Click any row to see the full answer and delete it.
        </p>
      </div>

      {/* Controls */}
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <Filter size={13} className="text-slate-400" />
          <span className="text-xs font-medium text-slate-500">Filter:</span>
          {filters.map((f) => (
            <button
              key={f.key}
              onClick={() => setRunTypeFilter(f.key)}
              className={`px-3 py-1 rounded-full text-xs font-semibold transition-colors ${
                runTypeFilter === f.key
                  ? 'bg-slate-800 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <Button
          variant="secondary"
          size="sm"
          iconLeft={<RefreshCw size={12} />}
          onClick={() => refetch()}
          loading={isLoading}
        >
          Refresh
        </Button>
      </div>

      {/* Content */}
      {isLoading ? (
        <Card className="p-8 flex items-center justify-center gap-3 text-slate-400">
          <Spinner size={16} /> Loading experiments…
        </Card>
      ) : isError ? (
        <Card accent="red" className="p-5">
          <p className="text-sm text-red-600">Failed to load experiment history.</p>
        </Card>
      ) : runs.length === 0 ? (
        <Card>
          <EmptyState
            icon={<History size={28} />}
            title="No experiments yet"
            description="Every question you ask or compare is saved here automatically."
          />
        </Card>
      ) : (
        <div>
          <p className="text-xs text-slate-400 mb-3">{data?.total ?? 0} runs</p>
          {runs.map((run) => (
            <RunRow
              key={run.id}
              run={run}
              onDelete={(id) => deleteMutation.mutate(id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
