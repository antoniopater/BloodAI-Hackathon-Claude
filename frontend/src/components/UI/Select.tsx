import { forwardRef, SelectHTMLAttributes, ReactNode, useId } from 'react'
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
          className="mb-1.5 block text-base font-semibold text-slate-800 dark:text-slate-100"
        >
          {label}
        </label>
      )}
      <select
        id={selectId}
        ref={ref}
        aria-invalid={error ? true : undefined}
        className={cn(
          'w-full min-h-[48px] rounded-xl border px-4 text-base',
          'bg-white text-slate-900 dark:bg-slate-900 dark:text-slate-100',
          'border-slate-300 dark:border-slate-600',
          'focus:outline-none focus:border-primary-700 focus:ring-4 focus:ring-primary-500/20',
          error && 'border-danger-500 focus:ring-danger-500/20',
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
