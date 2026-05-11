/**
 * EvaluationPage — aggregated evaluation dashboard.
 *
 * Shows:
 *   - Overall stats across all experiment runs
 *   - Per-template leaderboard
 *   - Score breakdowns per dimension
 *   - Benchmark runner (run all 15 questions against one template)
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  BarChart3,
  Trophy,
  FlaskConical,
  Play,
  CheckCircle2,
  ArrowRight,
} from 'lucide-react'
import { api } from '../api/client'
import type { ExperimentStats, PromptTemplate, BenchmarkRunResponse } from '../types'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Spinner from '../components/ui/Spinner'
import EmptyState from '../components/ui/EmptyState'

// ── Score bar ─────────────────────────────────────────────────────────────────

function MiniScoreBar({
  value,
  label,
  inverted = false,
}: {
  value: number
  label: string
  inverted?: boolean
}) {
  const pct = Math.round(value * 100)
  const display = inverted ? 100 - pct : pct
  const barColor =
    display >= 75 ? 'bg-emerald-500'
    : display >= 50 ? 'bg-blue-500'
    : display >= 30 ? 'bg-amber-500'
    : 'bg-red-500'

  return (
    <div>
      <div className="flex justify-between text-xs mb-0.5">
        <span className="text-slate-600">{label}</span>
        <span className="font-mono font-semibold text-slate-700">
          {inverted ? `${pct}% risk` : `${pct}%`}
        </span>
      </div>
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${barColor}`}
          style={{ width: `${display}%` }}
        />
      </div>
    </div>
  )
}

// ── Template leaderboard row ──────────────────────────────────────────────────

function LeaderboardRow({
  rank,
  name,
  runCount,
  avgScore,
}: {
  rank: number
  name: string
  runCount: number
  avgScore: number
}) {
  const pct = Math.round(avgScore * 100)
  const medal =
    rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : `${rank}.`

  return (
    <div className="flex items-center gap-3 py-2.5 border-b border-slate-100 last:border-0">
      <span className="w-8 text-center text-base">{medal}</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-slate-800 truncate">{name}</p>
        <p className="text-xs text-slate-400">{runCount} run{runCount !== 1 ? 's' : ''}</p>
      </div>
      <div className="flex items-center gap-2">
        <div className="w-20 h-2 bg-slate-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full ${
              pct >= 70 ? 'bg-emerald-500' : pct >= 50 ? 'bg-blue-500' : 'bg-amber-500'
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="text-xs font-bold font-mono text-slate-700 w-8 text-right">
          {pct}
        </span>
      </div>
    </div>
  )
}

// ── Benchmark runner ──────────────────────────────────────────────────────────

function BenchmarkRunner() {
  const [templateId, setTemplateId] = useState('technical')
  const [topK, setTopK] = useState(5)
  const [result, setResult] = useState<BenchmarkRunResponse | null>(null)
  const queryClient = useQueryClient()

  const { data: promptsData } = useQuery({
    queryKey: ['prompts'],
    queryFn: api.getPrompts,
  })

  const mutation = useMutation<
    BenchmarkRunResponse,
    Error,
    { templateId: string; topK: number }
  >({
    mutationFn: ({ templateId, topK }) => api.runBenchmark(templateId, topK),
    onSuccess: (data) => {
      setResult(data)
      queryClient.invalidateQueries({ queryKey: ['experiments', 'stats'] })
    },
  })

  return (
    <Card className="p-5">
      <div className="flex items-center gap-2 mb-4">
        <FlaskConical size={16} className="text-violet-600" />
        <h3 className="text-sm font-bold text-slate-800">Run Benchmark</h3>
        <span className="text-xs text-slate-400 ml-1">15 engineering questions</span>
      </div>

      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="flex-1 min-w-0">
          <label className="text-xs font-medium text-slate-600 block mb-1">Template</label>
          <select
            value={templateId}
            onChange={(e) => setTemplateId(e.target.value)}
            className="w-full text-sm border border-slate-300 rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-violet-500"
          >
            {(promptsData?.templates ?? []).map((t: PromptTemplate) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs font-medium text-slate-600 block mb-1">Top-K</label>
          <select
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            className="text-sm border border-slate-300 rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-violet-500"
          >
            {[3, 5, 8].map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
        </div>
        <div className="self-end">
          <Button
            variant="primary"
            size="sm"
            loading={mutation.isPending}
            iconLeft={mutation.isPending ? undefined : <Play size={13} />}
            onClick={() => mutation.mutate({ templateId, topK })}
            className="bg-violet-600 hover:bg-violet-700"
          >
            {mutation.isPending ? 'Running…' : 'Run Benchmark'}
          </Button>
        </div>
      </div>

      {mutation.isError && (
        <p className="text-sm text-red-600">{mutation.error.message}</p>
      )}

      {result && (
        <div className="mt-3 p-4 bg-emerald-50 border border-emerald-200 rounded-xl">
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle2 size={15} className="text-emerald-600" />
            <span className="text-sm font-bold text-emerald-800">
              Benchmark complete — {result.total_questions} questions
            </span>
          </div>
          <div className="grid grid-cols-3 gap-3 mb-3">
            <div className="text-center">
              <p className="text-2xl font-bold text-emerald-700">
                {Math.round(result.avg_overall_score * 100)}
              </p>
              <p className="text-xs text-slate-500">Avg Overall</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-slate-800">{result.total_questions}</p>
              <p className="text-xs text-slate-500">Questions</p>
            </div>
            <div className="text-center">
              <p className="text-sm font-bold text-slate-800">{result.template_name}</p>
              <p className="text-xs text-slate-500">Template</p>
            </div>
          </div>
          <div className="space-y-1.5">
            {result.results.slice(0, 5).map((r) => (
              <div key={r.question_id} className="flex items-center gap-2 text-xs">
                <Badge variant={r.difficulty === 'easy' ? 'success' : r.difficulty === 'medium' ? 'warning' : 'error'}>
                  {r.difficulty}
                </Badge>
                <span className="text-slate-600 flex-1 truncate">{r.question}</span>
                <span className="font-bold font-mono text-slate-700">
                  {Math.round(r.overall_score * 100)}
                </span>
              </div>
            ))}
            {result.results.length > 5 && (
              <p className="text-xs text-slate-400">
                +{result.results.length - 5} more — view in Experiment History
              </p>
            )}
          </div>
        </div>
      )}
    </Card>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function EvaluationPage() {
  const navigate = useNavigate()

  const { data: stats, isLoading, isError } = useQuery<ExperimentStats>({
    queryKey: ['experiments', 'stats'],
    queryFn: api.getExperimentStats,
    refetchInterval: 30_000,
  })

  const hasData = stats && stats.total_runs > 0

  return (
    <div className="max-w-5xl mx-auto px-8 py-8">

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-1">
          <BarChart3 size={20} className="text-violet-600" />
          <h1 className="text-2xl font-bold text-slate-900">Evaluation Dashboard</h1>
        </div>
        <p className="text-slate-500 text-sm">
          Aggregated evaluation scores across all Ask and Compare runs.
          Use the benchmark runner to test all 15 engineering questions at once.
        </p>
      </div>

      {/* ── Stats ──────────────────────────────────────────────────────── */}
      {isLoading ? (
        <Card className="p-8 flex items-center justify-center gap-3 text-slate-400 mb-6">
          <Spinner size={16} /> Loading evaluation data…
        </Card>
      ) : isError ? (
        <Card accent="red" className="p-5 mb-6">
          <p className="text-sm text-red-600">Could not load evaluation stats.</p>
        </Card>
      ) : !hasData ? (
        <Card className="mb-6">
          <EmptyState
            icon={<BarChart3 size={28} />}
            title="No evaluation data yet"
            description="Ask a question or run a comparison to start collecting evaluation scores."
            action={{
              label: 'Ask a Question',
              onClick: () => navigate('/ask'),
              icon: <ArrowRight size={13} />,
            }}
          />
        </Card>
      ) : (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            {[
              { label: 'Total Runs',    value: stats.total_runs,                      unit: 'experiments' },
              { label: 'Avg Overall',   value: Math.round(stats.avg_overall_score * 100), unit: '/ 100'   },
              { label: 'Avg Grounded',  value: Math.round(stats.avg_groundedness * 100),  unit: '/ 100'   },
              { label: 'Avg Relevance', value: Math.round(stats.avg_relevance * 100),     unit: '/ 100'   },
            ].map((s) => (
              <Card key={s.label} className="p-4">
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">{s.label}</p>
                <p className="text-2xl font-bold text-slate-900 mt-1 leading-none">{s.value}</p>
                <p className="text-xs text-slate-400 mt-1">{s.unit}</p>
              </Card>
            ))}
          </div>

          {/* Score breakdown + template leaderboard */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            {/* Score breakdown */}
            <Card className="p-5">
              <h3 className="text-sm font-bold text-slate-800 mb-4">Average Scores by Dimension</h3>
              <div className="space-y-3">
                <MiniScoreBar value={stats.avg_groundedness}        label="Groundedness"       />
                <MiniScoreBar value={stats.avg_relevance}           label="Relevance"           />
                <MiniScoreBar value={stats.avg_completeness}        label="Completeness"        />
                <MiniScoreBar value={stats.avg_clarity}             label="Clarity"             />
                <MiniScoreBar value={stats.avg_hallucination_risk}  label="Hallucination Risk"  inverted />
              </div>
            </Card>

            {/* Template leaderboard */}
            <Card className="p-5">
              <div className="flex items-center gap-2 mb-4">
                <Trophy size={15} className="text-amber-500" />
                <h3 className="text-sm font-bold text-slate-800">Template Leaderboard</h3>
              </div>
              {stats.by_template.length === 0 ? (
                <p className="text-xs text-slate-400">No template-tracked runs yet. Use Compare or ask with a template_id.</p>
              ) : (
                <div>
                  {stats.by_template.map((row, i) => (
                    <LeaderboardRow
                      key={row.template_name}
                      rank={i + 1}
                      name={row.template_name}
                      runCount={row.run_count}
                      avgScore={row.avg_score ?? 0}
                    />
                  ))}
                </div>
              )}
            </Card>
          </div>
        </>
      )}

      {/* ── Benchmark runner ────────────────────────────────────────────── */}
      <BenchmarkRunner />

      {/* Link to history */}
      <div className="mt-4 text-center">
        <button
          onClick={() => navigate('/experiments')}
          className="text-sm text-slate-500 hover:text-blue-600 flex items-center gap-1 mx-auto"
        >
          View full Experiment History <ArrowRight size={13} />
        </button>
      </div>
    </div>
  )
}
