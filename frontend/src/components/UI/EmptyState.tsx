import { ReactNode } from 'react'
import { cn } from '../../utils/cn'

interface EmptyStateProps {
  icon?: ReactNode
  title: ReactNode
  description?: ReactNode
  action?: ReactNode
  className?: string
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center text-center gap-3 py-10 px-6',
        'rounded-2xl border border-dashed border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/40',
        className,
      )}
    >
      {icon && (
        <div className="rounded-full bg-white dark:bg-slate-700 p-3 text-primary-700 dark:text-primary-100 shadow-sm" aria-hidden="true">
          {icon}
        </div>
      )}
      <h3 className="text-lg font-bold text-slate-900 dark:text-slate-50">{title}</h3>
      {description && (
        <p className="max-w-md text-base text-slate-600 dark:text-slate-300">{description}</p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
