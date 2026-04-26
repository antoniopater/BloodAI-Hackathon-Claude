import { useState } from 'react'
import {
  AlertTriangle,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Info,
  Siren,
} from 'lucide-react'
import type { ClinicalAlert } from '../../types/medical'

interface AlertCardProps {
  alert: ClinicalAlert
}

const SEVERITY_STYLES: Record<
  ClinicalAlert['severity'],
  { ring: string; bg: string; iconColor: string; label: string; Icon: typeof Info }
> = {
  critical: {
    ring: 'ring-2 ring-red-500',
    bg: 'bg-red-50 dark:bg-red-950/40',
    iconColor: 'text-red-600 dark:text-red-300',
    label: 'CRITICAL',
    Icon: Siren,
  },
  urgent: {
    ring: 'ring-2 ring-orange-500',
    bg: 'bg-orange-50 dark:bg-orange-950/40',
    iconColor: 'text-orange-600 dark:text-orange-300',
    label: 'URGENT',
    Icon: AlertTriangle,
  },
  warning: {
    ring: 'ring-1 ring-amber-400',
    bg: 'bg-amber-50 dark:bg-amber-950/30',
    iconColor: 'text-amber-600 dark:text-amber-300',
    label: 'WARNING',
    Icon: AlertCircle,
  },
  info: {
    ring: 'ring-1 ring-sky-300',
    bg: 'bg-sky-50 dark:bg-sky-950/30',
    iconColor: 'text-sky-600 dark:text-sky-300',
    label: 'INFO',
    Icon: Info,
  },
}

const TYPE_LABEL: Record<ClinicalAlert['alert_type'], string> = {
  velocity: 'Rate of change',
  threshold: 'Threshold crossing',
  pattern: 'Multi-parameter pattern',
  acceleration: 'Trend acceleration',
}

export function AlertCard({ alert }: AlertCardProps) {
  const [open, setOpen] = useState(alert.severity === 'critical')
  const style = SEVERITY_STYLES[alert.severity]
  const { Icon } = style

  return (
    <div
      role="alert"
      aria-live={alert.severity === 'critical' ? 'assertive' : 'polite'}
      className={`rounded-2xl ${style.bg} ${style.ring} p-4 shadow-sm`}
    >
      <div className="flex items-start gap-3">
        <Icon className={`mt-0.5 h-5 w-5 flex-shrink-0 ${style.iconColor}`} aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`text-xs font-bold uppercase tracking-wide ${style.iconColor}`}
            >
              {style.label}
            </span>
            <span className="text-xs text-slate-500 dark:text-slate-400">
              · {TYPE_LABEL[alert.alert_type]} · {alert.parameter}
            </span>
          </div>
          <h3 className="mt-1 text-base font-semibold text-slate-900 dark:text-slate-50">
            {alert.title}
          </h3>
          <p className="mt-1 text-sm text-slate-700 dark:text-slate-200">
            {alert.description}
          </p>

          {open && (
            <div className="mt-3 space-y-2 border-t border-slate-200 pt-3 dark:border-slate-700">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  Clinical significance
                </p>
                <p className="mt-0.5 text-sm text-slate-800 dark:text-slate-100">
                  {alert.clinical_significance}
                </p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  Recommended action
                </p>
                <p className="mt-0.5 text-sm text-slate-800 dark:text-slate-100">
                  {alert.recommended_action}
                </p>
              </div>
            </div>
          )}

          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-slate-50"
            aria-expanded={open}
          >
            {open ? (
              <>
                Less <ChevronUp className="h-3 w-3" aria-hidden="true" />
              </>
            ) : (
              <>
                Details <ChevronDown className="h-3 w-3" aria-hidden="true" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
