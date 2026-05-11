import { NavLink } from 'react-router-dom'
import {
  Cpu,
  LayoutDashboard,
  Upload,
  FolderOpen,
  Search,
  MessageSquare,
  GitCompare,
  BarChart3,
  History,
  CheckCircle2,
  XCircle,
  Loader2,
  Brain,
  Zap,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'

// ── Navigation structure ───────────────────────────────────────────────────────

const NAV_SECTIONS = [
  {
    label: 'Knowledge',
    items: [
      { to: '/',          icon: LayoutDashboard, label: 'Dashboard'         },
      { to: '/upload',    icon: Upload,          label: 'Upload Documents'  },
      { to: '/documents', icon: FolderOpen,      label: 'Document Library'  },
    ],
  },
  {
    label: 'Query',
    items: [
      { to: '/search', icon: Search,       label: 'Semantic Search'     },
      { to: '/ask',    icon: MessageSquare, label: 'Ask a Question'     },
    ],
  },
  {
    label: 'Experiment',
    items: [
      { to: '/compare',     icon: GitCompare, label: 'Compare Prompts'    },
      { to: '/evaluation',  icon: BarChart3,  label: 'Eval Dashboard'     },
      { to: '/experiments', icon: History,    label: 'Experiment History' },
    ],
  },
]

// ── NavItem ────────────────────────────────────────────────────────────────────

function NavItem({
  to,
  icon: Icon,
  label,
}: {
  to: string
  icon: React.ElementType
  label: string
}) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      className={({ isActive }) =>
        [
          'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150',
          isActive
            ? 'bg-blue-600 text-white shadow-sm'
            : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/70',
        ].join(' ')
      }
    >
      <Icon size={17} className="shrink-0" />
      <span>{label}</span>
    </NavLink>
  )
}

// ── Health status footer ───────────────────────────────────────────────────────

function HealthStatus() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['health'],
    queryFn: api.getHealth,
    refetchInterval: 30_000,
    retry: 1,
  })

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-slate-500 text-xs">
        <Loader2 size={13} className="animate-spin" />
        Connecting…
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="flex items-center gap-2 text-red-400 text-xs">
        <XCircle size={13} />
        Backend offline
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-emerald-400 text-xs">
        <CheckCircle2 size={13} />
        <span>Backend online · v{data.version}</span>
      </div>
      <div className="flex items-center gap-2 text-slate-400 text-xs">
        {data.llm_available ? (
          <>
            <Brain size={13} className="text-blue-400" />
            <span className="text-blue-400">LLM enabled</span>
          </>
        ) : (
          <>
            <Zap size={13} className="text-amber-400" />
            <span className="text-amber-400">Retrieval mode</span>
          </>
        )}
      </div>
      <div className="flex items-center gap-2 text-slate-500 text-xs pt-0.5">
        <span>{data.indexed_documents} docs · {data.total_chunks} chunks</span>
      </div>
    </div>
  )
}

// ── Sidebar ────────────────────────────────────────────────────────────────────

export default function Sidebar() {
  return (
    <aside className="w-60 shrink-0 bg-gradient-to-b from-slate-900 to-slate-950 flex flex-col h-screen sticky top-0 border-r border-slate-800">

      {/* Brand */}
      <div className="px-4 py-5 border-b border-slate-800">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center shadow-sm">
            <Cpu size={16} className="text-white" />
          </div>
          <div>
            <div className="text-white font-semibold text-sm leading-none">EngRAG</div>
            <div className="text-slate-500 text-xs mt-0.5">Knowledge Assistant</div>
          </div>
        </div>
      </div>

      {/* Navigation sections */}
      <nav className="flex-1 px-3 py-4 overflow-y-auto space-y-4">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label}>
            <p className="text-xs font-semibold text-slate-600 uppercase tracking-wider px-3 mb-1">
              {section.label}
            </p>
            <div className="space-y-0.5">
              {section.items.map((item) => (
                <NavItem key={item.to} {...item} />
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer: health */}
      <div className="px-4 py-4 border-t border-slate-800">
        <div className="text-xs text-slate-600 font-medium uppercase tracking-wider mb-2">
          System
        </div>
        <HealthStatus />
      </div>
    </aside>
  )
}
