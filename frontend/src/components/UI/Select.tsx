import { forwardRef, SelectHTMLAttributes, ReactNode, useId } from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '../../utils/cn'

export interface SelectOption {
  value: string
  label: string
}

export interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
  label?: ReactNode
  hint?: ReactNode
  error?: string | null
  options: SelectOption[]
  placeholder?: string
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, hint, error, options, placeholder, id, className, ...rest },
  ref,
) {
  const generatedId = useId()
  const selectId = id ?? generatedId
  return (
    <div className="w-full">
      {label && (
        <label
          htmlFor={selectId}
          className="mb-1.5 block text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400"
        >
          {label}
        </label>
      )}
      <div className="relative">
        <select
          id={selectId}
          ref={ref}
          aria-invalid={error ? true : undefined}
          className={cn(
            'w-full min-h-[48px] appearance-none rounded-xl border px-4 pr-10 text-base',
            'bg-white text-slate-900 dark:bg-slate-900 dark:text-slate-100',
            'border-slate-200 dark:border-slate-700',
            'shadow-sm hover:border-primary-400 dark:hover:border-primary-600',
            'transition-colors duration-150 cursor-pointer',
            'focus:outline-none focus:border-primary-600 focus:ring-4 focus:ring-primary-500/20',
            error && 'border-danger-500 focus:border-danger-500 focus:ring-danger-500/20',
            className,
          )}
          {...rest}
        >
          {placeholder && (
            <option value="" disabled>
              {placeholder}
            </option>
          )}
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <ChevronDown
          className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400 dark:text-slate-500"
          aria-hidden="true"
        />
      </div>
      {hint && !error && (
        <p className="mt-1.5 text-sm text-slate-600 dark:text-slate-400">{hint}</p>
      )}
      {error && (
        <p role="alert" className="mt-1.5 text-sm font-medium text-danger-700 dark:text-danger-500">
          {error}
        </p>
      )}
    </div>
  )
})
