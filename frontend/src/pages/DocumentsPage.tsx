import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  FolderOpen,
  Search,
  Trash2,
  Upload,
  Layers,
  Calendar,
  RefreshCw,
} from 'lucide-react'
import { api } from '../api/client'
import type { DocumentInfo } from '../types'
import { formatDate, FILE_TYPE_CONFIG } from '../types'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Spinner from '../components/ui/Spinner'
import EmptyState from '../components/ui/EmptyState'
import ConfirmDialog from '../components/ui/ConfirmDialog'

// ── Document card ─────────────────────────────────────────────────────────────

function DocumentCard({
  doc,
  onDelete,
}: {
  doc: DocumentInfo
  onDelete: (docId: string) => void
}) {
  const cfg = FILE_TYPE_CONFIG[doc.file_type] ?? FILE_TYPE_CONFIG.txt

  // Reconstruct a readable display name from doc_id
  // doc_id format: {stem}_{ext}_{hash6}  →  strip last two segments
  const parts = doc.doc_id.split('_')
  const displayName =
    parts.length >= 3
      ? parts.slice(0, -2).join('_') + '.' + parts[parts.length - 2]
      : doc.doc_id

  return (
    <Card hover className="p-5 flex flex-col gap-4">
      {/* Top row: type badge + doc name */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <Badge variant="filetype" fileType={doc.file_type}>
            {doc.file_type.toUpperCase()}
          </Badge>
          {/* Subtle delete trigger */}
          <button
            onClick={() => onDelete(doc.doc_id)}
            className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors"
            title="Delete document"
          >
            <Trash2 size={13} />
          </button>
        </div>
        <p className="text-sm font-semibold text-slate-800 leading-snug break-all">
          {displayName}
        </p>
        <p className="text-xs font-mono text-slate-400 mt-0.5 truncate">{doc.doc_id}</p>
      </div>

      {/* Stats */}
      <div className="flex items-center gap-4 text-xs text-slate-500">
        <span className={`flex items-center gap-1 font-medium px-1.5 py-0.5 rounded-md ${cfg.bg} ${cfg.text}`}>
          <Layers size={11} />
          {doc.chunks} chunks
        </span>
        <span className="flex items-center gap-1">
          <Calendar size={11} />
          {formatDate(doc.ingested_at)}
        </span>
      </div>
    </Card>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function DocumentsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<string | null>(null)
  const [deletingDocId, setDeletingDocId] = useState<string | null>(null)

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['documents'],
    queryFn: api.getDocuments,
  })

  const deleteMutation = useMutation({
    mutationFn: api.deleteDocument,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] })
      queryClient.invalidateQueries({ queryKey: ['health'] })
      setDeletingDocId(null)
    },
  })

  // ── Filter logic ────────────────────────────────────────────────────
  const allDocs = data?.documents ?? []
  const availableTypes = [...new Set(allDocs.map((d) => d.file_type))].sort()

  const filtered: DocumentInfo[] = allDocs.filter((doc) => {
    const matchesSearch =
      search === '' ||
      doc.doc_id.toLowerCase().includes(search.toLowerCase())
    const matchesType = typeFilter === null || doc.file_type === typeFilter
    return matchesSearch && matchesType
  })

  // ── Render ──────────────────────────────────────────────────────────
  return (
    <div className="max-w-5xl mx-auto px-8 py-8">

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Document Library</h1>
          <p className="text-slate-500 mt-1 text-sm">
            {data
              ? `${data.total_documents} document${data.total_documents !== 1 ? 's' : ''} · ${data.total_chunks} total chunks`
              : 'Browse and manage indexed documents'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            iconLeft={isFetching ? <Spinner size={13} /> : <RefreshCw size={13} />}
            onClick={() => refetch()}
            disabled={isFetching}
          >
            Refresh
          </Button>
          <Button
            variant="primary"
            size="sm"
            iconLeft={<Upload size={13} />}
            onClick={() => navigate('/upload')}
          >
            Upload
          </Button>
        </div>
      </div>

      {/* ── Filter bar ─────────────────────────────────────────────── */}
      {allDocs.length > 0 && (
        <div className="flex items-center gap-3 mb-5">
          {/* Search input */}
          <div className="relative flex-1 max-w-sm">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Filter by document name…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-8 pr-3 py-2 text-sm bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Type filters */}
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setTypeFilter(null)}
              className={`px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                typeFilter === null
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-slate-600 border border-slate-300 hover:bg-slate-50'
              }`}
            >
              All
            </button>
            {availableTypes.map((t) => (
              <button
                key={t}
                onClick={() => setTypeFilter(typeFilter === t ? null : t)}
                className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                  typeFilter === t
                    ? 'bg-blue-600 text-white'
                    : 'bg-white text-slate-600 border border-slate-300 hover:bg-slate-50'
                }`}
              >
                .{t}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Loading state ─────────────────────────────────────────── */}
      {isLoading && (
        <div className="flex items-center justify-center py-20 gap-3 text-slate-400">
          <Spinner size={18} />
          <span className="text-sm">Loading documents…</span>
        </div>
      )}

      {/* ── Error state ────────────────────────────────────────────── */}
      {isError && (
        <Card accent="red" className="p-6">
          <p className="text-sm font-medium text-red-700">Failed to load documents</p>
          <p className="text-sm text-slate-500 mt-1">{(error as Error).message}</p>
          <Button
            variant="secondary"
            size="sm"
            className="mt-3"
            onClick={() => refetch()}
          >
            Retry
          </Button>
        </Card>
      )}

      {/* ── Empty state ────────────────────────────────────────────── */}
      {!isLoading && !isError && allDocs.length === 0 && (
        <Card>
          <EmptyState
            icon={<FolderOpen size={28} />}
            title="No documents indexed yet"
            description="Upload engineering files to build your knowledge base. Supported: .txt, .md, .log, .pdf"
            action={{
              label: 'Upload your first document',
              icon: <Upload size={14} />,
              onClick: () => navigate('/upload'),
            }}
          />
        </Card>
      )}

      {/* ── Search no-results ──────────────────────────────────────── */}
      {!isLoading && !isError && allDocs.length > 0 && filtered.length === 0 && (
        <div className="text-center py-12 text-slate-400 text-sm">
          No documents match <strong>"{search}"</strong>
        </div>
      )}

      {/* ── Document grid ──────────────────────────────────────────── */}
      {filtered.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((doc) => (
            <DocumentCard
              key={doc.doc_id}
              doc={doc}
              onDelete={(id) => setDeletingDocId(id)}
            />
          ))}
        </div>
      )}

      {/* ── Delete confirmation ─────────────────────────────────────── */}
      <ConfirmDialog
        open={deletingDocId !== null}
        title="Delete document?"
        description={`All ${
          allDocs.find((d) => d.doc_id === deletingDocId)?.chunks ?? ''
        } chunks for "${deletingDocId}" will be permanently removed from the index.`}
        confirmLabel="Delete document"
        loading={deleteMutation.isPending}
        onConfirm={() => deletingDocId && deleteMutation.mutate(deletingDocId)}
        onCancel={() => setDeletingDocId(null)}
      />
    </div>
  )
}
