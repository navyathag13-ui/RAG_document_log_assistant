import { FILE_TYPE_CONFIG } from '../../types'

type BadgeVariant = 'default' | 'success' | 'warning' | 'error' | 'info' | 'filetype'

interface BadgeProps {
  children: React.ReactNode
  variant?: BadgeVariant
  fileType?: string    // only used when variant='filetype'
  className?: string
}

const variantClasses: Record<Exclude<BadgeVariant, 'filetype'>, string> = {
  default: 'bg-slate-100 text-slate-700',
  success: 'bg-emerald-100 text-emerald-700',
  warning: 'bg-amber-100 text-amber-700',
  error:   'bg-red-100 text-red-700',
  info:    'bg-blue-100 text-blue-700',
}

export default function Badge({
  children,
  variant = 'default',
  fileType,
  className = '',
}: BadgeProps) {
  let colorClasses = variantClasses[variant as Exclude<BadgeVariant, 'filetype'>] ?? variantClasses.default

  if (variant === 'filetype' && fileType) {
    const cfg = FILE_TYPE_CONFIG[fileType.toLowerCase()]
    if (cfg) colorClasses = `${cfg.bg} ${cfg.text}`
  }

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold tracking-wide uppercase ${colorClasses} ${className}`}
    >
      {children}
    </span>
  )
}
