import { ReactNode, useId, useState } from 'react'
import { HelpCircle } from 'lucide-react'
import { cn } from '../../utils/cn'

interface TooltipProps {
  content: ReactNode
  children?: ReactNode
  className?: string
  label?: string
}

/**
 * Accessible tooltip that reveals on hover AND keyboard focus. When no children
 * are provided, renders a small help-circle button (for inline help).
 */
export function Tooltip({ content, children, className, label = 'Show help' }: TooltipProps) {
  const [open, setOpen] = useState(false)
  const id = useId()
  const tipId = `tip-${id}`

  const show = () => setOpen(true)
  const hide = () => setOpen(false)

  const trigger = children ?? (
    <button
      type="button"
      aria-label={label}
      className="inline-flex items-center justify-center min-h-[32px] min-w-[32px] rounded-full text-slate-500 hover:text-primary-700 hover:bg-slate-100 dark:hover:bg-slate-700"
    >
      <HelpCircle className="h-5 w-5" aria-hidden="true" />
    </button>
  )

  return (
    <span
      className={cn('relative inline-flex items-center', className)}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
      aria-describedby={open ? tipId : undefined}
    >
      {trigger}
      {open && (
        <span
          role="tooltip"
          id={tipId}
          className="absolute left-1/2 top-full z-30 mt-2 w-64 -translate-x-1/2 rounded-lg bg-slate-900 px-3 py-2 text-sm text-white shadow-lg dark:bg-slate-700"
        >
          {content}
        </span>
      )}
    </span>
  )
}
