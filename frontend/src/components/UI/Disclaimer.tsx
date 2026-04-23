import { Info } from 'lucide-react'
import { MEDICAL_DISCLAIMER } from '../../utils/constants'
import { cn } from '../../utils/cn'

interface DisclaimerProps {
  compact?: boolean
  className?: string
}

export function Disclaimer({ compact, className }: DisclaimerProps) {
  return (
    <div
      role="note"
      className={cn(
        'flex items-start gap-3 rounded-xl border border-primary-100 bg-primary-50 px-4 py-3',
        'dark:border-primary-700/50 dark:bg-primary-800/20',
        className,
      )}
    >
      <Info className="mt-0.5 h-5 w-5 flex-shrink-0 text-primary-700 dark:text-primary-100" aria-hidden="true" />
      <p
        className={cn(
          'text-primary-900 dark:text-primary-100',
          compact ? 'text-sm' : 'text-sm sm:text-base',
        )}
      >
        {MEDICAL_DISCLAIMER}
      </p>
    </div>
  )
}
