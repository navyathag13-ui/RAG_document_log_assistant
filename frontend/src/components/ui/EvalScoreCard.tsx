/**
 * EvalScoreCard — displays the 5-dimension evaluation scores for one answer.
 *
 * Each dimension is shown as a labelled progress bar.
 * Hallucination Risk is special: lower is better, shown in red when high.
 */

interface Dimension {
  label: string
  value: number
  description: string
  /** If true, a lower value is better (inverted colour scale). */
  invertedScale?: boolean
}

function ScoreDimension({ label, value, description, invertedScale = false }: Dimension) {
  const pct = Math.round(value * 100)
  const display = invertedScale ? 100 - pct : pct

  // Colour based on display (already inverted for risk)
  const barColor =
    display >= 75 ? 'bg-emerald-500'
    : display >= 50 ? 'bg-blue-500'
    : display >= 30 ? 'bg-amber-500'
    : 'bg-red-500'

  const textColor =
    display >= 75 ? 'text-emerald-700'
    : display >= 50 ? 'text-blue-700'
    : display >= 30 ? 'text-amber-700'
    : 'text-red-600'

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <div>
          <span className="text-xs font-semibold text-slate-700">{label}</span>
          <span className="ml-1.5 text-xs text-slate-400">{description}</span>
        </div>
        <span className={`text-xs font-bold font-mono ${textColor}`}>
          {invertedScale
            ? `${pct}% risk`
            : `${pct}%`}
        </span>
      </div>
      <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${display}%` }}
        />
      </div>
    </div>
  )
}

// ── Overall score ring ────────────────────────────────────────────────────────

function OverallRing({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color =
    pct >= 75 ? 'text-emerald-600' : pct >= 50 ? 'text-blue-600' : pct >= 30 ? 'text-amber-600' : 'text-red-500'
  const ring =
    pct >= 75 ? 'ring-emerald-500' : pct >= 50 ? 'ring-blue-500' : pct >= 30 ? 'ring-amber-500' : 'ring-red-400'

  return (
    <div className={`w-14 h-14 rounded-full ring-4 ${ring} flex flex-col items-center justify-center shrink-0`}>
      <span className={`text-lg font-bold leading-none ${color}`}>{pct}</span>
      <span className="text-xs text-slate-400 leading-none">/ 100</span>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export interface EvalScores {
  groundedness_score: number
  relevance_score: number
  completeness_score: number
  clarity_score: number
  hallucination_risk: number
  overall_score: number
  method?: string
}

interface EvalScoreCardProps {
  scores: EvalScores
  /** If provided, shown as a sub-heading */
  label?: string
  className?: string
}

export default function EvalScoreCard({ scores, label, className = '' }: EvalScoreCardProps) {
  const dimensions: Dimension[] = [
    {
      label: 'Groundedness',
      value: scores.groundedness_score,
      description: 'answer supported by context',
    },
    {
      label: 'Relevance',
      value: scores.relevance_score,
      description: 'chunk similarity scores',
    },
    {
      label: 'Completeness',
      value: scores.completeness_score,
      description: 'question fully addressed',
    },
    {
      label: 'Clarity',
      value: scores.clarity_score,
      description: 'structure & readability',
    },
    {
      label: 'Hallucination Risk',
      value: scores.hallucination_risk,
      description: 'unsupported specific claims',
      invertedScale: true,
    },
  ]

  return (
    <div className={`bg-white rounded-xl border border-slate-200 shadow-sm p-4 ${className}`}>
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <OverallRing score={scores.overall_score} />
        <div>
          {label && (
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-0.5">
              {label}
            </p>
          )}
          <p className="text-sm font-bold text-slate-800">Answer Quality</p>
          <p className="text-xs text-slate-400">
            {scores.method === 'rule_based' ? 'Rule-based evaluation' : 'LLM-as-judge'}
          </p>
        </div>
      </div>

      {/* Dimension bars */}
      <div className="space-y-2.5">
        {dimensions.map((d) => (
          <ScoreDimension key={d.label} {...d} />
        ))}
      </div>
    </div>
  )
}
