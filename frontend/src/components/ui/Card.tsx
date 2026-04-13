interface CardProps {
  children: React.ReactNode
  className?: string
  /** Add a colored left border accent (design affordance for status) */
  accent?: 'blue' | 'emerald' | 'amber' | 'red' | 'slate'
  hover?: boolean
  onClick?: () => void
}

const accentClasses: Record<string, string> = {
  blue:    'border-l-4 border-l-blue-500',
  emerald: 'border-l-4 border-l-emerald-500',
  amber:   'border-l-4 border-l-amber-500',
  red:     'border-l-4 border-l-red-500',
  slate:   'border-l-4 border-l-slate-400',
}

export default function Card({ children, className = '', accent, hover, onClick }: CardProps) {
  return (
    <div
      onClick={onClick}
      className={[
        'bg-white rounded-xl border border-slate-200 shadow-sm',
        hover ? 'hover:shadow-md hover:border-slate-300 transition-all duration-150' : '',
        accent ? accentClasses[accent] : '',
        onClick ? 'cursor-pointer' : '',
        className,
      ].join(' ')}
    >
      {children}
    </div>
  )
}
