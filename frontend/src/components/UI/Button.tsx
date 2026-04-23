import { forwardRef, ButtonHTMLAttributes, ReactNode } from 'react'
import { cn } from '../../utils/cn'
import { Loader2 } from 'lucide-react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'success'
type Size = 'md' | 'lg' | 'xl'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
  leftIcon?: ReactNode
  rightIcon?: ReactNode
  fullWidth?: boolean
}

const variantClasses: Record<Variant, string> = {
  primary:
    'bg-primary-700 hover:bg-primary-800 active:bg-primary-900 text-white shadow-sm ' +
    'disabled:bg-slate-300 disabled:text-slate-500 dark:disabled:bg-slate-700 dark:disabled:text-slate-500',
  secondary:
    'bg-white border border-slate-300 hover:bg-slate-50 active:bg-slate-100 text-slate-900 ' +
    'dark:bg-slate-800 dark:border-slate-600 dark:text-slate-100 dark:hover:bg-slate-700',
  ghost:
    'bg-transparent hover:bg-slate-100 active:bg-slate-200 text-slate-900 ' +
    'dark:hover:bg-slate-800 dark:text-slate-100',
  danger:
    'bg-danger-500 hover:bg-danger-700 text-white shadow-sm disabled:bg-slate-300',
  success:
    'bg-success-500 hover:bg-success-700 text-white shadow-sm disabled:bg-slate-300',
}

const sizeClasses: Record<Size, string> = {
  md: 'min-h-[44px] px-4 text-base',
  lg: 'min-h-[48px] px-5 text-lg',
  xl: 'min-h-[56px] px-6 text-lg',
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = 'primary',
    size = 'lg',
    loading = false,
    leftIcon,
    rightIcon,
    fullWidth,
    className,
    children,
    disabled,
    type = 'button',
    ...rest
  },
  ref,
) {
  const isDisabled = disabled || loading
  return (
    <button
      ref={ref}
      type={type}
      aria-busy={loading || undefined}
      aria-disabled={isDisabled || undefined}
      disabled={isDisabled}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-xl font-semibold',
        'transition-colors duration-150 select-none',
        'focus:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/40',
        'disabled:cursor-not-allowed',
        variantClasses[variant],
        sizeClasses[size],
        fullWidth && 'w-full',
        className,
      )}
      {...rest}
    >
      {loading ? (
        <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
      ) : leftIcon ? (
        <span className="flex-shrink-0" aria-hidden="true">
          {leftIcon}
        </span>
      ) : null}
      <span>{children}</span>
      {!loading && rightIcon ? (
        <span className="flex-shrink-0" aria-hidden="true">
          {rightIcon}
        </span>
      ) : null}
    </button>
  )
})
