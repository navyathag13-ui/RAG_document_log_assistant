import { scoreBarColor, scoreLabel, scoreColor } from '../../types'

interface ScoreBarProps {
  score: number
  showLabel?: boolean
  compact?: boolean
}

/**
 * Visual similarity-score indicator.
 * Shows a colour-coded progress bar plus the numeric value.
 * Colour thresholds: ≥0.75 emerald, ≥0.55 blue, ≥0.35 amber, else slate.
 */
export default function ScoreBar({ score, showLabel = false, compact = false }: ScoreBarProps) {
  const pct = Math.min(100, Math.max(0, Math.round(score * 100)))
  const barColor = scoreBarColor(score)
  const textColor = scoreColor(score)

  if (compact) {
    return (
      <span className={`font-mono text-xs font-semibold ${textColor}`}>
        {score.toFixed(2)}
      </span>
    )
  }

  return (
    <div className="flex items-center gap-2 w-full">
      {/* Bar track */}
      <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {/* Numeric value */}
      <span className={`font-mono text-xs font-semibold w-9 text-right shrink-0 ${textColor}`}>
        {score.toFixed(2)}
      </span>
      {showLabel && (
        <span className={`text-xs shrink-0 ${textColor}`}>
          {scoreLabel(score)}
        </span>
      )}
    </div>
  )
}
