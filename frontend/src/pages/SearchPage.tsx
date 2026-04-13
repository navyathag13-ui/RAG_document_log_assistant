import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { Search, ChevronDown, ChevronUp, Upload } from 'lucide-react'
import { api } from '../api/client'
import type { ChunkResult, SearchResponse } from '../types'
import { scoreColor, scoreBarColor } from '../types'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import ScoreBar from '../components/ui/ScoreBar'
import EmptyState from '../components/ui/EmptyState'
import Spinner from '../components/ui/Spinner'

const EXAMPLE_QUERIES = [
  'hydraulic pump overheating causes',
  'voltage calibration thresholds EDC',
  'sensor communication fault restart steps',
  'pressure drop troubleshooting',
  'heat exchanger cooling fan failure',
]

const TOP_K_OPTIONS = [3, 5, 8, 10]

// ── Single result card ───────────────────────────────────────────────────────

function ResultCard({ result, rank }: { result: ChunkResult; rank: number }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <Card className="overflow-hidden animate-slide-up">
      {/* Header row */}
      <div className="flex items-start gap-4 p-4 border-b border-slate-100">
        {/* Rank badge */}
        <div className="w-7 h-7 rounded-full bg-slate-100 text-slate-500 text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
          {rank}
        </div>

        <div className="flex-1 min-w-0">
          {/* Doc name + type */}
          <div className="flex items-center gap-2 flex-wrap mb-1.5">
            <Badge variant="filetype" fileType={result.file_type}>
              {result.file_type.toUpperCase()}
            </Badge>
            <span className="text-sm font-semibold text-slate-700 truncate">
              {result.doc_name}
            </span>
            <span className="text-xs text-slate-400 font-mono">
              chunk #{result.chunk_index}
            </span>
          </div>

          {/* Score bar */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 shrink-0">Relevance</span>
            <ScoreBar score={result.score} />
          </div>
        </div>
      </div>

      {/* Chunk text */}
      <div className="p-4">
        <p
          className={`text-sm text-slate-700 leading-relaxed whitespace-pre-wrap font-mono text-xs ${
            expanded ? '' : 'line-clamp-4'
          }`}
        >
          {result.text}
        </p>

        {result.text.length > 300 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="mt-2 flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium"
          >
            {expanded ? (
              <>
                <ChevronUp size={12} /> Show less
              </>
            ) : (
              <>
                <ChevronDown size={12} /> Show full chunk
              </>
            )}
          </button>
        )}
      </div>

      {/* Score footer */}
      <div className="px-4 py-2.5 bg-slate-50 border-t border-slate-100 flex items-center justify-between">
        <span className="text-xs font-mono text-slate-400 truncate">{result.chunk_id}</span>
        <span
          className={`text-xs font-bold font-mono ${scoreColor(result.score)}`}
        >
          {(result.score * 100).toFixed(1)}% match
        </span>
      </div>
    </Card>
  )
}

// ── Score distribution mini-chart ────────────────────────────────────────────

function ScoreDistribution({ results }: { results: ChunkResult[] }) {
  return (
    <div className="flex items-end gap-1 h-8">
      {results.map((r, i) => (
        <div
          key={r.chunk_id}
          title={`#${i + 1}: ${r.score.toFixed(3)}`}
          className={`flex-1 rounded-t-sm transition-all ${scoreBarColor(r.score)}`}
          style={{ height: `${Math.max(20, r.score * 100)}%` }}
        />
      ))}
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function SearchPage() {
  const navigate = useNavigate()

  const [query, setQuery] = useState('')
  const [topK, setTopK] = useState(5)
  const [searchResponse, setSearchResponse] = useState<SearchResponse | null>(null)

  const searchMutation = useMutation<SearchResponse, Error, { query: string; topK: number }>({
    mutationFn: ({ query, topK }) => api.search(query, topK),
    onSuccess: (data) => setSearchResponse(data),
  })

  const handleSearch = () => {
    const q = query.trim()
    if (!q) return
    setSearchResponse(null)
    searchMutation.mutate({ query: q, topK })
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSearch()
    }
  }

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <div className="max-w-4xl mx-auto px-8 py-8">

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Semantic Search</h1>
        <p className="text-slate-500 mt-1 text-sm">
          Retrieve the most relevant document chunks using natural language queries.
          Results are ranked by cosine similarity score.
        </p>
      </div>

      {/* ── Search input card ───────────────────────────────────────── */}
      <Card className="p-5 mb-6">
        {/* Input */}
        <div className="relative">
          <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search across all indexed documents…"
            className="w-full pl-10 pr-4 py-2.5 text-sm bg-slate-50 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent focus:bg-white transition-colors"
          />
        </div>

        {/* Options row */}
        <div className="flex items-center justify-between mt-3 flex-wrap gap-3">
          {/* Top-K selector */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 font-medium">Top results:</span>
            <div className="flex items-center gap-1">
              {TOP_K_OPTIONS.map((n) => (
                <button
                  key={n}
                  onClick={() => setTopK(n)}
                  className={`w-8 h-7 rounded-md text-xs font-semibold transition-colors ${
                    topK === n
                      ? 'bg-blue-600 text-white'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>

          <Button
            variant="primary"
            loading={searchMutation.isPending}
            iconLeft={<Search size={14} />}
            onClick={handleSearch}
            disabled={!query.trim()}
          >
            {searchMutation.isPending ? 'Searching…' : 'Search'}
          </Button>
        </div>

        {/* Example query chips */}
        {!searchResponse && !searchMutation.isPending && (
          <div className="mt-3 pt-3 border-t border-slate-100">
            <p className="text-xs text-slate-400 mb-2">Try:</p>
            <div className="flex flex-wrap gap-1.5">
              {EXAMPLE_QUERIES.map((q) => (
                <button
                  key={q}
                  onClick={() => {
                    setQuery(q)
                    setSearchResponse(null)
                    searchMutation.mutate({ query: q, topK })
                  }}
                  className="px-2.5 py-1 bg-slate-100 hover:bg-blue-50 hover:text-blue-700 text-slate-600 rounded-full text-xs transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
      </Card>

      {/* ── Loading ─────────────────────────────────────────────────── */}
      {searchMutation.isPending && (
        <div className="flex items-center justify-center py-16 gap-3 text-slate-400">
          <Spinner size={18} />
          <span className="text-sm">Searching {topK} most relevant chunks…</span>
        </div>
      )}

      {/* ── Error ───────────────────────────────────────────────────── */}
      {searchMutation.isError && (
        <Card accent="red" className="p-5">
          <p className="text-sm font-medium text-red-700">Search failed</p>
          <p className="text-sm text-slate-500 mt-1">{searchMutation.error.message}</p>
          {searchMutation.error.message.includes('No documents') && (
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

      {/* ── Results ─────────────────────────────────────────────────── */}
      {searchResponse && !searchMutation.isPending && (
        <div className="animate-fade-in">
          {/* Results meta bar */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <h2 className="text-sm font-semibold text-slate-700">
                {searchResponse.total_results} chunk{searchResponse.total_results !== 1 ? 's' : ''} retrieved
              </h2>
              <span className="text-xs text-slate-400">
                for "{searchResponse.query}"
              </span>
            </div>
            {/* Mini score distribution */}
            {searchResponse.results.length > 1 && (
              <div className="w-32">
                <ScoreDistribution results={searchResponse.results} />
              </div>
            )}
          </div>

          {/* Empty results */}
          {searchResponse.results.length === 0 ? (
            <Card>
              <EmptyState
                icon={<Search size={28} />}
                title="No matching chunks"
                description="Try a different query or ingest more documents."
              />
            </Card>
          ) : (
            <div className="space-y-3">
              {searchResponse.results.map((r, i) => (
                <ResultCard key={r.chunk_id} result={r} rank={i + 1} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
