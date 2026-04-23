import { HTMLAttributes, ReactNode } from 'react'
import { cn } from '../../utils/cn'
import type { ParameterStatus } from '../../types/medical'

type Tone = 'neutral' | 'success' | 'warning' | 'danger' | 'info'

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone
  size?: 'sm' | 'md'
  icon?: ReactNode
}

const toneClasses: Record<Tone, string> = {
  neutral:
    'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-100',
  success:
    'bg-success-50 text-success-700 dark:bg-success-700/20 dark:text-success-500',
  warning:
    'bg-warning-50 text-warning-700 dark:bg-warning-700/20 dark:text-warning-500',
  danger:
    'bg-danger-50 text-danger-700 dark:bg-danger-700/20 dark:text-danger-500',
  info: 'bg-primary-50 text-primary-700 dark:bg-primary-800/30 dark:text-primary-100',
}

export function Badge({ tone = 'neutral', size = 'md', icon, className, children, ...rest }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full font-semibold',
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm',
        toneClasses[tone],
        className,
      )}
      {...rest}
    >
      {icon && <span aria-hidden="true">{icon}</span>}
      {children}
    </span>
  )
}

export function statusToTone(status: ParameterStatus): Tone {
  switch (status) {
    case 'normal':
      return 'success'
    case 'low':
      return 'warning'
    case 'high':
      return 'warning'
    case 'critical':
      return 'danger'
    case 'unknown':
      return 'neutral'
  }
}
