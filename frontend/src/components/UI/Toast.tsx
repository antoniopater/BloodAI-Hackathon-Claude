import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from 'lucide-react'
import { useToastStore, type Toast, type ToastKind } from '../../store/useToastStore'
import { cn } from '../../utils/cn'

const iconByKind: Record<ToastKind, React.ReactNode> = {
  success: <CheckCircle2 className="h-5 w-5 text-success-500" aria-hidden="true" />,
  error: <AlertCircle className="h-5 w-5 text-danger-500" aria-hidden="true" />,
  info: <Info className="h-5 w-5 text-primary-700 dark:text-primary-100" aria-hidden="true" />,
  warning: <AlertTriangle className="h-5 w-5 text-warning-500" aria-hidden="true" />,
}

const toneByKind: Record<ToastKind, string> = {
  success: 'border-success-500/30',
  error: 'border-danger-500/40',
  info: 'border-primary-500/30',
  warning: 'border-warning-500/40',
}

function ToastCard({ toast }: { toast: Toast }) {
  const dismiss = useToastStore((s) => s.dismiss)
  return (
    <div
      role={toast.kind === 'error' ? 'alert' : 'status'}
      aria-live={toast.kind === 'error' ? 'assertive' : 'polite'}
      className={cn(
        'pointer-events-auto flex items-start gap-3 rounded-xl border bg-white dark:bg-slate-800',
        'shadow-lg px-4 py-3 min-w-[280px] max-w-md',
        toneByKind[toast.kind],
      )}
    >
      <div className="flex-shrink-0 pt-0.5">{iconByKind[toast.kind]}</div>
      <div className="flex-1 min-w-0">
        {toast.title && (
          <p className="text-base font-semibold text-slate-900 dark:text-slate-50">{toast.title}</p>
        )}
        <p className="text-sm text-slate-700 dark:text-slate-200">{toast.message}</p>
      </div>
      <button
        type="button"
        onClick={() => dismiss(toast.id)}
        aria-label="Dismiss notification"
        className="flex-shrink-0 rounded-md p-1 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700 min-h-[32px] min-w-[32px] flex items-center justify-center"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}

export function ToastHost() {
  const toasts = useToastStore((s) => s.toasts)
  return (
    <div
      className="fixed top-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none"
      aria-label="Notifications"
    >
      {toasts.map((t) => (
        <ToastCard key={t.id} toast={t} />
      ))}
    </div>
  )
}
