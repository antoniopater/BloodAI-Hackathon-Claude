import { ReactNode, useId } from 'react'
import { cn } from '../../utils/cn'

export interface Tab<T extends string> {
  id: T
  label: ReactNode
  icon?: ReactNode
  badge?: ReactNode
}

interface TabsProps<T extends string> {
  tabs: Array<Tab<T>>
  value: T
  onChange: (id: T) => void
  label?: string
  className?: string
  variant?: 'pill' | 'underline'
}

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
  label,
  className,
  variant = 'pill',
}: TabsProps<T>) {
  const groupId = useId()

  return (
    <div
      role="tablist"
      aria-label={label ?? 'Tabs'}
      className={cn(
        'inline-flex gap-1 p-1',
        variant === 'pill' &&
          'rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700',
        variant === 'underline' && 'border-b border-slate-200 dark:border-slate-700 w-full',
        className,
      )}
    >
      {tabs.map((tab) => {
        const active = tab.id === value
        return (
          <button
            key={tab.id}
            id={`${groupId}-${tab.id}`}
            role="tab"
            type="button"
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(tab.id)}
            className={cn(
              'inline-flex items-center gap-2 min-h-[44px] px-4 text-base font-semibold transition-colors',
              'focus:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/40',
              variant === 'pill' && 'rounded-lg',
              variant === 'pill' && active && 'bg-white dark:bg-slate-700 text-primary-800 dark:text-primary-100 shadow-sm',
              variant === 'pill' && !active && 'text-slate-600 dark:text-slate-300 hover:bg-slate-200/50 dark:hover:bg-slate-700/50',
              variant === 'underline' &&
                (active
                  ? 'border-b-2 border-primary-700 text-primary-800 dark:text-primary-100 -mb-px'
                  : 'border-b-2 border-transparent text-slate-600 dark:text-slate-300 hover:text-slate-900'),
            )}
          >
            {tab.icon && (
              <span className="flex-shrink-0" aria-hidden="true">
                {tab.icon}
              </span>
            )}
            <span>{tab.label}</span>
            {tab.badge && <span className="ml-1">{tab.badge}</span>}
          </button>
        )
      })}
    </div>
  )
}
