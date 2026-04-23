import { forwardRef, InputHTMLAttributes, ReactNode, useId } from 'react'
import { cn } from '../../utils/cn'
import { AlertCircle } from 'lucide-react'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: ReactNode
  hint?: ReactNode
  error?: string | null
  rightSlot?: ReactNode
  /** Fills the right side of the input label row (e.g., a status Badge). */
  labelSlot?: ReactNode
  /** Normally-rendered label text for non-"floating" inputs. */
  suffix?: ReactNode
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, error, rightSlot, labelSlot, suffix, id, className, disabled, ...rest },
  ref,
) {
  const generatedId = useId()
  const inputId = id ?? generatedId
  const hintId = hint ? `${inputId}-hint` : undefined
  const errorId = error ? `${inputId}-error` : undefined
  const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined

  return (
    <div className="w-full">
      {(label || labelSlot) && (
        <div className="mb-1.5 flex items-center justify-between gap-2">
          {label && (
            <label htmlFor={inputId} className="text-base font-semibold text-slate-800 dark:text-slate-100">
              {label}
            </label>
          )}
          {labelSlot}
        </div>
      )}
      <div className="relative">
        <input
          ref={ref}
          id={inputId}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          disabled={disabled}
          className={cn(
            'w-full min-h-[48px] rounded-xl border px-4 text-base',
            'bg-white text-slate-900 placeholder:text-slate-400',
            'dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500',
            'border-slate-300 dark:border-slate-600',
            'focus:outline-none focus:border-primary-700 focus:ring-4 focus:ring-primary-500/20',
            'disabled:bg-slate-100 disabled:text-slate-500 disabled:cursor-not-allowed',
            'dark:disabled:bg-slate-800',
            error && 'border-danger-500 focus:border-danger-500 focus:ring-danger-500/20',
            (rightSlot || suffix) && 'pr-20',
            className,
          )}
          {...rest}
        />
        {(rightSlot || suffix) && (
          <div className="absolute inset-y-0 right-0 flex items-center gap-1 pr-3 text-sm text-slate-500 pointer-events-none">
            {suffix}
            {rightSlot}
          </div>
        )}
      </div>
      {hint && !error && (
        <p id={hintId} className="mt-1.5 text-sm text-slate-600 dark:text-slate-400">
          {hint}
        </p>
      )}
      {error && (
        <p
          id={errorId}
          role="alert"
          className="mt-1.5 flex items-center gap-1.5 text-sm font-medium text-danger-700 dark:text-danger-500"
        >
          <AlertCircle className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
          {error}
        </p>
      )}
    </div>
  )
})
