import { useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Upload,
  FileText,
  CheckCircle2,
  AlertCircle,
  X,
  FolderOpen,
  FileType,
  RefreshCw,
} from 'lucide-react'
import { api } from '../api/client'
import type { IngestResponse } from '../types'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'

const ACCEPTED_TYPES = ['.txt', '.md', '.log', '.pdf']
const ACCEPTED_MIME =
  'text/plain,text/markdown,text/x-log,application/pdf,application/octet-stream'

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1_048_576).toFixed(1)} MB`
}

function fileTypeFromName(name: string): string {
  return name.split('.').pop()?.toLowerCase() ?? 'txt'
}

export default function UploadPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [isDragging, setIsDragging] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [result, setResult] = useState<IngestResponse | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const mutation = useMutation<IngestResponse, Error, File>({
    mutationFn: api.ingestFile,
    onSuccess: (data) => {
      setResult(data)
      setSelectedFile(null)
      setUploadError(null)
      // Invalidate cached queries so Documents page and Dashboard refresh
      queryClient.invalidateQueries({ queryKey: ['documents'] })
      queryClient.invalidateQueries({ queryKey: ['health'] })
    },
    onError: (err) => {
      setUploadError(err.message)
    },
  })

  // ── Drag handlers ──────────────────────────────────────────────────────────
  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const onDragLeave = useCallback((e: React.DragEvent) => {
    // Only clear when leaving the drop zone itself, not a child
    if (!(e.currentTarget as HTMLElement).contains(e.relatedTarget as Node)) {
      setIsDragging(false)
    }
  }, [])

  const handleFiles = useCallback((files: FileList | null) => {
    if (!files || files.length === 0) return
    const file = files[0]
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!ACCEPTED_TYPES.includes(ext)) {
      setUploadError(
        `"${file.name}" is not a supported type. Please upload ${ACCEPTED_TYPES.join(', ')}.`
      )
      return
    }
    setUploadError(null)
    setResult(null)
    setSelectedFile(file)
  }, [])

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setIsDragging(false)
      handleFiles(e.dataTransfer.files)
    },
    [handleFiles]
  )

  const handleReset = () => {
    setSelectedFile(null)
    setResult(null)
    setUploadError(null)
    mutation.reset()
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="max-w-2xl mx-auto px-8 py-8">

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Upload Documents</h1>
        <p className="text-slate-500 mt-1 text-sm">
          Add engineering manuals, troubleshooting guides, system logs, or internal notes.
          Each file is chunked, embedded, and stored in the vector database.
        </p>
      </div>

      {/* ── Success state ──────────────────────────────────────────────── */}
      {result && (
        <Card accent="emerald" className="p-6 mb-6 animate-slide-up">
          <div className="flex items-start gap-4">
            <CheckCircle2 size={22} className="text-emerald-500 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-slate-900">
                Document ingested successfully
              </p>
              <p className="text-sm text-slate-500 mt-0.5">{result.message}</p>
              <div className="flex flex-wrap gap-2 mt-3">
                <div className="flex items-center gap-1.5 bg-slate-100 rounded-lg px-2.5 py-1 text-xs text-slate-700">
                  <FileType size={12} />
                  <span className="font-medium">Type:</span> {result.file_type.toUpperCase()}
                </div>
                <div className="flex items-center gap-1.5 bg-slate-100 rounded-lg px-2.5 py-1 text-xs text-slate-700">
                  <span className="font-medium">Chunks created:</span> {result.chunks_created}
                </div>
                <div className="flex items-center gap-1.5 bg-slate-100 rounded-lg px-2.5 py-1 text-xs font-mono text-slate-600 max-w-xs overflow-hidden text-ellipsis whitespace-nowrap">
                  ID: {result.doc_id}
                </div>
              </div>
              <div className="flex gap-2 mt-4">
                <Button
                  size="sm"
                  variant="secondary"
                  iconLeft={<FolderOpen size={13} />}
                  onClick={() => navigate('/documents')}
                >
                  View in Library
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  iconLeft={<RefreshCw size={13} />}
                  onClick={handleReset}
                >
                  Upload Another
                </Button>
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* ── Error state ────────────────────────────────────────────────── */}
      {uploadError && (
        <Card accent="red" className="p-4 mb-6 animate-fade-in">
          <div className="flex items-start gap-3">
            <AlertCircle size={16} className="text-red-500 shrink-0 mt-0.5" />
            <p className="text-sm text-red-700">{uploadError}</p>
            <button className="ml-auto" onClick={() => setUploadError(null)}>
              <X size={14} className="text-red-400 hover:text-red-600" />
            </button>
          </div>
        </Card>
      )}

      {/* ── Drop zone ──────────────────────────────────────────────────── */}
      {!result && (
        <Card className="mb-6">
          <div
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            onClick={() => !selectedFile && fileInputRef.current?.click()}
            className={[
              'relative rounded-xl border-2 border-dashed transition-all duration-200 cursor-pointer',
              isDragging
                ? 'border-blue-500 bg-blue-50'
                : selectedFile
                ? 'border-blue-300 bg-blue-50/40 cursor-default'
                : 'border-slate-300 bg-slate-50 hover:border-blue-400 hover:bg-blue-50/30',
              'p-12',
            ].join(' ')}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_MIME}
              className="hidden"
              onChange={(e) => handleFiles(e.target.files)}
            />

            {selectedFile ? (
              /* File preview */
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-white border border-slate-200 shadow-sm flex items-center justify-center shrink-0">
                  <FileText size={22} className="text-blue-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-slate-800 truncate">
                    {selectedFile.name}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <Badge variant="filetype" fileType={fileTypeFromName(selectedFile.name)}>
                      {fileTypeFromName(selectedFile.name).toUpperCase()}
                    </Badge>
                    <span className="text-xs text-slate-400">{formatBytes(selectedFile.size)}</span>
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    setSelectedFile(null)
                  }}
                  className="w-7 h-7 rounded-lg bg-slate-100 hover:bg-red-100 flex items-center justify-center transition-colors"
                >
                  <X size={13} className="text-slate-500 hover:text-red-500" />
                </button>
              </div>
            ) : (
              /* Empty drop zone */
              <div className="flex flex-col items-center text-center">
                <div
                  className={`w-14 h-14 rounded-2xl flex items-center justify-center mb-4 transition-colors ${
                    isDragging ? 'bg-blue-100' : 'bg-slate-100'
                  }`}
                >
                  <Upload
                    size={26}
                    className={isDragging ? 'text-blue-500' : 'text-slate-400'}
                  />
                </div>
                <p className="text-sm font-semibold text-slate-700 mb-1">
                  {isDragging ? 'Drop to upload' : 'Drag & drop or click to browse'}
                </p>
                <p className="text-xs text-slate-400">
                  Supports {ACCEPTED_TYPES.join(', ')}
                </p>
              </div>
            )}
          </div>

          {/* Actions row */}
          {selectedFile && (
            <div className="px-6 pb-5 pt-4 border-t border-slate-100 flex items-center justify-between">
              <p className="text-xs text-slate-400">
                File will be chunked, embedded, and stored in ChromaDB
              </p>
              <Button
                variant="primary"
                loading={mutation.isPending}
                onClick={() => mutation.mutate(selectedFile)}
                iconLeft={<Upload size={14} />}
              >
                {mutation.isPending ? 'Indexing…' : 'Index Document'}
              </Button>
            </div>
          )}
        </Card>
      )}

      {/* ── Accepted formats reference ─────────────────────────────────── */}
      <Card className="p-5">
        <h3 className="text-xs font-semibold text-slate-700 uppercase tracking-wider mb-3">
          Supported File Types
        </h3>
        <div className="grid grid-cols-2 gap-3">
          {[
            { ext: 'txt', label: 'Plain Text',    desc: 'Operations manuals, reports'   },
            { ext: 'md',  label: 'Markdown',       desc: 'Engineering notes, wiki pages' },
            { ext: 'log', label: 'Log Files',      desc: 'System logs, event records'    },
            { ext: 'pdf', label: 'PDF Documents',  desc: 'Scanned or native PDFs'        },
          ].map(({ ext, label, desc }) => (
            <div
              key={ext}
              className="flex items-start gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100"
            >
              <Badge variant="filetype" fileType={ext} className="mt-0.5">
                .{ext}
              </Badge>
              <div>
                <p className="text-xs font-medium text-slate-700">{label}</p>
                <p className="text-xs text-slate-400">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
