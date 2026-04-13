import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  FolderOpen,
  Layers,
  Brain,
  Activity,
  Upload,
  MessageSquare,
  Search,
  ArrowRight,
  FileText,
  Cpu,
} from 'lucide-react'
import { api } from '../api/client'
import { formatDate } from '../types'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Spinner from '../components/ui/Spinner'

// ── Stat card ─────────────────────────────────────────────────────────────────

interface StatCardProps {
  label: string
  value: string | number
  icon: React.ReactNode
  iconBg: string
  sub?: string
}

function StatCard({ label, value, icon, iconBg, sub }: StatCardProps) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">{label}</p>
          <p className="text-2xl font-bold text-slate-900 mt-1.5 leading-none">{value}</p>
          {sub && <p className="text-xs text-slate-400 mt-1.5">{sub}</p>}
        </div>
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${iconBg}`}>
          {icon}
        </div>
      </div>
    </Card>
  )
}

// ── Quick-action card ──────────────────────────────────────────────────────────

interface QuickActionProps {
  title: string
  description: string
  icon: React.ReactNode
  iconBg: string
  label: string
  onClick: () => void
}

function QuickAction({ title, description, icon, iconBg, label, onClick }: QuickActionProps) {
  return (
    <Card hover className="p-5 cursor-pointer group" onClick={onClick}>
      <div className="flex items-start gap-4">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${iconBg}`}>
          {icon}
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
          <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">{description}</p>
        </div>
        <ArrowRight
          size={16}
          className="text-slate-300 group-hover:text-blue-500 group-hover:translate-x-0.5 transition-all shrink-0 mt-0.5"
        />
      </div>
      <div className="mt-3 pt-3 border-t border-slate-100">
        <span className="text-xs font-medium text-blue-600">{label}</span>
      </div>
    </Card>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const navigate = useNavigate()

  const { data: health, isLoading: healthLoading, isError: healthError } = useQuery({
    queryKey: ['health'],
    queryFn: api.getHealth,
    refetchInterval: 30_000,
  })

  const { data: docs } = useQuery({
    queryKey: ['documents'],
    queryFn: api.getDocuments,
  })

  const recentDocs = docs?.documents.slice(0, 4) ?? []

  return (
    <div className="max-w-5xl mx-auto px-8 py-8">

      {/* ── Hero ──────────────────────────────────────────────────────── */}
      <div className="mb-8">
        <div className="flex items-center gap-2.5 mb-2">
          <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center">
            <Cpu size={14} className="text-white" />
          </div>
          <span className="text-xs font-semibold text-blue-600 uppercase tracking-wider">
            Engineering RAG Assistant
          </span>
        </div>
        <h1 className="text-3xl font-bold text-slate-900 leading-tight">
          Knowledge Dashboard
        </h1>
        <p className="text-slate-500 mt-1.5 text-base">
          Upload engineering documents, search indexed content, and get grounded answers backed by your source files.
        </p>
      </div>

      {/* ── Stats ─────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {healthLoading ? (
          <Card className="col-span-4 p-8 flex items-center justify-center gap-3 text-slate-400">
            <Spinner size={16} /> Fetching system status…
          </Card>
        ) : healthError ? (
          <Card accent="red" className="col-span-4 p-5">
            <p className="text-sm font-medium text-red-600">Backend unreachable</p>
            <p className="text-xs text-slate-500 mt-0.5">
              Make sure the FastAPI server is running on port 8000.
            </p>
          </Card>
        ) : health ? (
          <>
            <StatCard
              label="Documents"
              value={health.indexed_documents}
              icon={<FolderOpen size={18} className="text-blue-600" />}
              iconBg="bg-blue-50"
              sub="indexed in vector store"
            />
            <StatCard
              label="Chunks"
              value={health.total_chunks}
              icon={<Layers size={18} className="text-violet-600" />}
              iconBg="bg-violet-50"
              sub="embedded text segments"
            />
            <StatCard
              label="LLM Synthesis"
              value={health.llm_available ? 'Enabled' : 'Fallback'}
              icon={<Brain size={18} className={health.llm_available ? 'text-emerald-600' : 'text-amber-600'} />}
              iconBg={health.llm_available ? 'bg-emerald-50' : 'bg-amber-50'}
              sub={health.llm_available ? 'OpenAI connected' : 'Retrieval-only mode'}
            />
            <StatCard
              label="System"
              value={health.status === 'healthy' ? 'Healthy' : health.status}
              icon={<Activity size={18} className="text-emerald-600" />}
              iconBg="bg-emerald-50"
              sub={`v${health.version}`}
            />
          </>
        ) : null}
      </div>

      {/* ── Quick actions ─────────────────────────────────────────────── */}
      <div className="mb-8">
        <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wider mb-3">
          Quick Actions
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <QuickAction
            title="Upload Documents"
            description="Add engineering manuals, guides, logs, or notes to the knowledge index."
            icon={<Upload size={18} className="text-blue-600" />}
            iconBg="bg-blue-50"
            label="Go to Upload →"
            onClick={() => navigate('/upload')}
          />
          <QuickAction
            title="Semantic Search"
            description="Find the most relevant chunks across all indexed content using natural language."
            icon={<Search size={18} className="text-violet-600" />}
            iconBg="bg-violet-50"
            label="Open Search →"
            onClick={() => navigate('/search')}
          />
          <QuickAction
            title="Ask a Question"
            description="Get grounded, source-linked answers from your documents using the RAG pipeline."
            icon={<MessageSquare size={18} className="text-emerald-600" />}
            iconBg="bg-emerald-50"
            label="Ask Now →"
            onClick={() => navigate('/ask')}
          />
        </div>
      </div>

      {/* ── How it works ──────────────────────────────────────────────── */}
      <div className="mb-8">
        <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wider mb-3">
          Workflow
        </h2>
        <Card className="p-5">
          <div className="flex flex-wrap items-center gap-0">
            {[
              { step: '01', label: 'Upload', desc: 'Add .txt, .md, .log, or .pdf files' },
              { step: '02', label: 'Index',  desc: 'Chunks embedded into vector store'  },
              { step: '03', label: 'Search', desc: 'Retrieve semantically similar chunks'},
              { step: '04', label: 'Answer', desc: 'LLM or retrieval-grounded response' },
            ].map((s, i, arr) => (
              <div key={s.step} className="flex items-center">
                <div className="flex items-center gap-3 px-4 py-2">
                  <div className="w-7 h-7 rounded-full bg-blue-600 text-white text-xs font-bold flex items-center justify-center shrink-0">
                    {s.step}
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-slate-800">{s.label}</div>
                    <div className="text-xs text-slate-500">{s.desc}</div>
                  </div>
                </div>
                {i < arr.length - 1 && (
                  <ArrowRight size={14} className="text-slate-300 shrink-0" />
                )}
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* ── Recent documents ──────────────────────────────────────────── */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wider">
            Indexed Documents
          </h2>
          {(docs?.total_documents ?? 0) > 0 && (
            <Button variant="ghost" size="sm" onClick={() => navigate('/documents')}>
              View all →
            </Button>
          )}
        </div>

        {recentDocs.length === 0 ? (
          <Card className="p-8 flex flex-col items-center text-center">
            <FileText size={32} className="text-slate-300 mb-3" />
            <p className="text-sm font-medium text-slate-600">No documents indexed yet</p>
            <p className="text-xs text-slate-400 mt-1 mb-4">
              Upload engineering files to start querying your knowledge base.
            </p>
            <Button variant="primary" size="sm" iconLeft={<Upload size={13} />} onClick={() => navigate('/upload')}>
              Upload your first document
            </Button>
          </Card>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {recentDocs.map((doc) => (
              <Card key={doc.doc_id} hover className="p-4">
                <div className="flex items-start justify-between mb-2">
                  <Badge variant="filetype" fileType={doc.file_type}>
                    {doc.file_type.toUpperCase()}
                  </Badge>
                  <span className="text-xs text-slate-400 font-mono">{doc.chunks} chunks</span>
                </div>
                <p className="text-sm font-medium text-slate-800 truncate">
                  {doc.doc_id.split('_').slice(0, -1).join('_') || doc.doc_id}
                </p>
                <p className="text-xs text-slate-400 mt-1">{formatDate(doc.ingested_at)}</p>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
