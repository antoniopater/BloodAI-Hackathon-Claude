import { useMemo } from 'react'
import type { DisplayMode } from '../../store/useAppStore'
import type { TriagePrediction } from '../../types/medical'
import { TRIAGE_LABELS } from '../../utils/constants'
import { formatPct } from '../../utils/formatters'
import { cn } from '../../utils/cn'
import { AlertOctagon } from 'lucide-react'

interface TriageResultsProps {
  predictions: TriagePrediction[]
  mode: DisplayMode
  onSelect?: (prediction: TriagePrediction) => void
  selectedClass?: string | null
}

function barTone(p: number): { bg: string; bar: string; label: string } {
  if (p >= 0.7)
    return {
      bg: 'bg-success-50 dark:bg-success-700/15',
      bar: 'bg-success-500',
      label: 'Strong match',
    }
  if (p >= 0.3)
    return {
      bg: 'bg-warning-50 dark:bg-warning-700/15',
      bar: 'bg-warning-500',
      label: 'Possible match',
    }
  return {
    bg: 'bg-slate-100 dark:bg-slate-700/30',
    bar: 'bg-slate-400',
    label: 'Low likelihood',
  }
}

export function TriageResults({ predictions, mode, onSelect, selectedClass }: TriageResultsProps) {
  const sorted = useMemo(
    () => [...predictions].sort((a, b) => b.probability - a.probability),
    [predictions],
  )

  const erPrediction = sorted.find((p) => p.class === 'ER')
  const highErRisk = erPrediction && erPrediction.probability >= 0.5

  return (
    <div className="space-y-3">
      {highErRisk && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-xl border-2 border-danger-500 bg-danger-50 px-4 py-3 dark:bg-danger-700/20"
        >
          <AlertOctagon className="h-6 w-6 flex-shrink-0 text-danger-700" aria-hidden="true" />
          <div>
            <p className="text-lg font-bold text-danger-700 dark:text-danger-500">
              Possible emergency
            </p>
            <p className="text-sm text-slate-800 dark:text-slate-100">
              The analysis suggests these results may require urgent attention. If you feel unwell,
              please go to the nearest Emergency Department or call emergency services.
            </p>
          </div>
        </div>
      )}

      <ul className="space-y-2" aria-label="Triage predictions">
        {sorted.map((p) => {
          const meta = TRIAGE_LABELS[p.class as keyof typeof TRIAGE_LABELS]
          if (!meta) return null
          const tone = barTone(p.probability)
          const pct = Math.round(p.probability * 100)
          const selected = selectedClass === p.class
          const interactive = Boolean(onSelect)
          const displayLabel = mode === 'patient' ? meta.patient : meta.en

          const content = (
            <>
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-xl" aria-hidden="true">
                    {meta.emoji}
                  </span>
                  <span className="truncate text-base font-semibold text-slate-900 dark:text-slate-50">
                    {displayLabel}
                  </span>
                  {selected && (
                    <span className="ml-1 rounded-full bg-primary-700 px-2 py-0.5 text-xs font-bold text-white">
                      Selected
                    </span>
                  )}
                </div>
                <span
                  className="text-sm font-bold tabular-nums text-slate-700 dark:text-slate-200"
                  aria-hidden="true"
                >
                  {formatPct(p.probability)}
                </span>
              </div>

              <div
                className={cn('mt-2 h-3 w-full overflow-hidden rounded-full', tone.bg)}
                aria-hidden="true"
              >
                <div
                  className={cn('h-full rounded-full transition-[width] duration-500', tone.bar)}
                  style={{ width: `${pct}%` }}
                />
              </div>
              {mode === 'clinical' && (
                <div className="mt-1 flex items-center justify-between gap-2 text-xs text-slate-500 dark:text-slate-400">
                  <span>{tone.label}</span>
                  {p.confidence != null && <span>Confidence {formatPct(p.confidence)}</span>}
                </div>
              )}
            </>
          )

          const ariaLabel = `${displayLabel}: ${pct} percent likelihood. ${tone.label}.`

          return (
            <li key={p.class}>
              {interactive ? (
                <button
                  type="button"
                  onClick={() => onSelect?.(p)}
                  aria-label={ariaLabel}
                  aria-pressed={selected}
                  className={cn(
                    'w-full rounded-xl border p-3 text-left transition-colors',
                    selected
                      ? 'border-primary-700 bg-primary-50 dark:bg-primary-800/30'
                      : 'border-slate-200 bg-white hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:hover:bg-slate-700/60',
                    'focus:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/40',
                  )}
                >
                  {content}
                </button>
              ) : (
                <div
                  aria-label={ariaLabel}
                  className="rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-800"
                >
                  {content}
                </div>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
