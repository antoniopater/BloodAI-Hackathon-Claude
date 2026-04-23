import { HTMLAttributes, ReactNode, forwardRef } from 'react'
import { cn } from '../../utils/cn'

export interface CardProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  padding?: 'sm' | 'md' | 'lg' | 'none'
  elevated?: boolean
  title?: ReactNode
  titleSlot?: ReactNode
  description?: ReactNode
}

const padMap = {
  none: '',
  sm: 'p-4',
  md: 'p-5 sm:p-6',
  lg: 'p-6 sm:p-8',
} as const

export const Card = forwardRef<HTMLDivElement, CardProps>(function Card(
  { padding = 'md', elevated, title, titleSlot, description, className, children, ...rest },
  ref,
) {
  return (
    <div
      ref={ref}
      className={cn(
        'rounded-2xl border bg-white border-slate-200 dark:bg-slate-800 dark:border-slate-700',
        elevated ? 'card-shadow-lg' : 'card-shadow',
        padMap[padding],
        className,
      )}
      {...rest}
    >
      {(title || description) && (
        <div className="mb-4 flex items-start justify-between gap-4">
          <div className="min-w-0">
            {title && (
              <h2 className="text-xl font-bold text-slate-900 dark:text-slate-50">{title}</h2>
            )}
            {description && (
              <p className="mt-1 text-base text-slate-600 dark:text-slate-300">{description}</p>
            )}
          </div>
          {titleSlot && <div className="flex-shrink-0">{titleSlot}</div>}
        </div>
      )}
      {children}
    </div>
  )
})
