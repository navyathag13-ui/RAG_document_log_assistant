import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import {
  MessageSquare,
  Brain,
  Zap,
  ChevronDown,
  ChevronUp,
  Upload,
  Send,
  BookOpen,
} from 'lucide-react'
import { api } from '../api/client'
import type { AskResponse, SourceChunk } from '../types'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import ScoreBar from '../components/ui/ScoreBar'
import Spinner from '../components/ui/Spinner'

const EXAMPLE_QUESTIONS = [
  'What should I check if the hydraulic pump overheats?',
  'What are the restart steps after a sensor communication fault?',
  'What does the log suggest about the failure cause on 2024-03-04?',
  'Which document mentions voltage calibration thresholds?',
  'Summarise the troubleshooting steps related to pressure drop alerts.',
]

const TOP_K_OPTIONS = [3, 5, 8, 10]

// ── Source chunk card ─────────────────────────────────────────────────────────

function SourceCard({ source, rank }: { source: SourceChunk; rank: number }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <Card className="overflow-hidden">
      {/* Header */}
      <div className="p-3 border-b border-slate-100 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-5 h-5 rounded bg-slate-100 text-slate-500 text-xs font-bold flex items-center justify-center shrink-0">
            {rank}
          </div>
          <Badge variant="filetype" fileType={source.file_type}>
            {source.file_type.toUpperCase()}
          </Badge>
          <span className="text-xs font-medium text-slate-700 truncate">
            {source.doc_name}
          </span>
        </div>
        <ScoreBar score={source.score} compact />
      </div>

      {/* Score bar */}
      <div className="px-3 py-2 bg-slate-50 border-b border-slate-100">
        <ScoreBar score={source.score} showLabel />
      </div>

      {/* Text excerpt */}
      <div className="p-3">
        <p
          className={`text-xs text-slate-600 leading-relaxed font-mono whitespace-pre-wrap ${
            expanded ? '' : 'line-clamp-3'
          }`}
        >
          {source.text_excerpt}
        </p>
        {source.text_excerpt.length >= 290 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="mt-1.5 flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium"
          >
            {expanded ? <><ChevronUp size={10} /> Less</> : <><ChevronDown size={10} /> More</>}
          </button>
        )}
      </div>
    </Card>
  )
}

// ── Answer panel ──────────────────────────────────────────────────────────────

function AnswerPanel({ result }: { result: AskResponse }) {
  const [sourcesOpen, setSourcesOpen] = useState(true)

  return (
    <div className="animate-slide-up space-y-4">

      {/* Answer card */}
      <Card accent={result.llm_used ? 'blue' : 'amber'} className="overflow-hidden">
        {/* Card header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-100 bg-slate-50/60">
          <div className="flex items-center gap-2">
            {result.llm_used ? (
              <>
                <Brain size={15} className="text-blue-500" />
                <span className="text-sm font-semibold text-slate-800">
                  LLM-synthesised answer
                </span>
              </>
            ) : (
              <>
                <Zap size={15} className="text-amber-500" />
                <span className="text-sm font-semibold text-slate-800">
                  Retrieval-grounded answer
                </span>
              </>
            )}
          </div>
          <div className="flex items-center gap-2">
            {result.llm_used ? (
              <Badge variant="info">LLM</Badge>
            ) : (
              <Badge variant="warning">Fallback</Badge>
            )}
            <span className="text-xs text-slate-400">
              {result.retrieval_count} source{result.retrieval_count !== 1 ? 's' : ''} retrieved
            </span>
          </div>
        </div>

        {/* Answer body */}
        <div className="p-5">
          <p className="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap">
            {result.answer}
          </p>
        </div>
      </Card>

      {/* Sources section */}
      {result.sources.length > 0 && (
        <div>
          {/* Sources toggle header */}
          <button
            onClick={() => setSourcesOpen(!sourcesOpen)}
            className="w-full flex items-center justify-between px-4 py-3 bg-white border border-slate-200 rounded-xl hover:bg-slate-50 transition-colors group"
          >
            <div className="flex items-center gap-2">
              <BookOpen size={15} className="text-slate-500" />
              <span className="text-sm font-semibold text-slate-700">
                Supporting Sources
              </span>
              <span className="bg-slate-100 text-slate-600 text-xs font-bold px-1.5 py-0.5 rounded-full">
                {result.sources.length}
              </span>
            </div>
            {sourcesOpen ? (
              <ChevronUp size={15} className="text-slate-400 group-hover:text-slate-600" />
            ) : (
              <ChevronDown size={15} className="text-slate-400 group-hover:text-slate-600" />
            )}
          </button>

          {sourcesOpen && (
            <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3 animate-fade-in">
              {result.sources.map((source, i) => (
                <SourceCard key={source.chunk_id} source={source} rank={i + 1} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function AskPage() {
  const navigate = useNavigate()

  const [question, setQuestion] = useState('')
  const [topK, setTopK] = useState(5)
  const [result, setResult] = useState<AskResponse | null>(null)

  const askMutation = useMutation<AskResponse, Error, { question: string; topK: number }>({
    mutationFn: ({ question, topK }) => api.ask(question, topK),
    onSuccess: (data) => setResult(data),
  })

  const handleAsk = () => {
    const q = question.trim()
    if (!q) return
    setResult(null)
    askMutation.mutate({ question: q, topK })
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      handleAsk()
    }
  }

  const handleExample = (q: string) => {
    setQuestion(q)
    setResult(null)
    askMutation.reset()
    askMutation.mutate({ question: q, topK })
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="max-w-4xl mx-auto px-8 py-8">

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Ask a Question</h1>
        <p className="text-slate-500 mt-1 text-sm">
          Get grounded answers from your indexed engineering documents.
          Every answer cites the exact source chunks it was drawn from.
        </p>
      </div>

      {/* ── Question input card ─────────────────────────────────────── */}
      <Card className="p-5 mb-6">

        {/* Textarea */}
        <div className="relative">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything about your indexed documents…&#10;e.g. What should I check if the hydraulic pump overheats?"
            rows={4}
            className="w-full px-4 py-3 text-sm bg-slate-50 border border-slate-300 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent focus:bg-white transition-colors leading-relaxed"
          />
          <p className="absolute bottom-2.5 right-3 text-xs text-slate-300 pointer-events-none">
            ⌘ Enter to submit
          </p>
        </div>

        {/* Controls row */}
        <div className="flex items-center justify-between mt-3 flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 font-medium">Sources to retrieve:</span>
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
            size="md"
            loading={askMutation.isPending}
            iconRight={askMutation.isPending ? undefined : <Send size={14} />}
            onClick={handleAsk}
            disabled={!question.trim()}
          >
            {askMutation.isPending ? 'Thinking…' : 'Ask Question'}
          </Button>
        </div>

        {/* Example questions */}
        {!result && !askMutation.isPending && (
          <div className="mt-3 pt-3 border-t border-slate-100">
            <p className="text-xs text-slate-400 mb-2">
              <MessageSquare size={11} className="inline mr-1" />
              Example questions:
            </p>
            <div className="flex flex-col gap-1.5">
              {EXAMPLE_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => handleExample(q)}
                  className="text-left px-3 py-2 text-xs text-slate-600 bg-slate-50 hover:bg-blue-50 hover:text-blue-700 rounded-lg transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
      </Card>

      {/* ── Loading state ───────────────────────────────────────────── */}
      {askMutation.isPending && (
        <Card className="p-8 flex flex-col items-center gap-4 animate-fade-in">
          <div className="w-12 h-12 rounded-2xl bg-blue-50 flex items-center justify-center">
            <Spinner size={22} className="text-blue-500" />
          </div>
          <div className="text-center">
            <p className="text-sm font-semibold text-slate-800">Searching your documents…</p>
            <p className="text-xs text-slate-400 mt-1">
              Embedding query · Retrieving {topK} chunks · Generating answer
            </p>
          </div>
        </Card>
      )}

      {/* ── Error state ─────────────────────────────────────────────── */}
      {askMutation.isError && (
        <Card accent="red" className="p-5 animate-fade-in">
          <p className="text-sm font-medium text-red-700">Could not generate an answer</p>
          <p className="text-sm text-slate-500 mt-1">{askMutation.error.message}</p>
          {askMutation.error.message.includes('No documents') && (
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

      {/* ── Answer panel ────────────────────────────────────────────── */}
      {result && !askMutation.isPending && (
        <AnswerPanel result={result} />
      )}
    </div>
  )
}
