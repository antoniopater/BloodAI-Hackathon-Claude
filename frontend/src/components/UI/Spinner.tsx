import { Loader2 } from 'lucide-react'
import { cn } from '../../utils/cn'

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  label?: string
  className?: string
}

const sizeMap = { sm: 'h-4 w-4', md: 'h-6 w-6', lg: 'h-10 w-10' }

export function Spinner({ size = 'md', label = 'Loading', className }: SpinnerProps) {
  return (
    <span role="status" aria-live="polite" className={cn('inline-flex items-center gap-2', className)}>
      <Loader2 className={cn('animate-spin text-primary-700 dark:text-primary-100', sizeMap[size])} aria-hidden="true" />
      <span className="sr-only">{label}</span>
    </span>
  )
}

export function FullPageSpinner({ label = 'Loading…' }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col items-center justify-center gap-4 py-16">
      <Loader2 className="h-12 w-12 animate-spin text-primary-700" aria-hidden="true" />
      <p className="text-base text-slate-700 dark:text-slate-200">{label}</p>
    </div>
  )
}
