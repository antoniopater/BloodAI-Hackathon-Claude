import { useMemo } from 'react'
import type { AttentionWeight } from '../../types/medical'
import { LAB_REFERENCE } from '../../utils/constants'
import { formatPct } from '../../utils/formatters'

interface AttentionHeatmapProps {
  weights: AttentionWeight[]
  /** Compact = used inline in cards. */
  compact?: boolean
}

/**
 * Renders attention weights as a horizontal bar chart.
 * Not a true token-level heatmap — acts as "which parameters mattered".
 */
export function AttentionHeatmap({ weights, compact }: AttentionHeatmapProps) {
  const sorted = useMemo(() => {
    const cloned = [...weights].filter((w) => typeof w.weight === 'number')
    cloned.sort((a, b) => b.weight - a.weight)
    return cloned.slice(0, compact ? 6 : 12)
  }, [weights, compact])

  const max = Math.max(0.0001, ...sorted.map((w) => w.weight))

  if (sorted.length === 0) {
    return (
      <div className="text-sm text-slate-600 dark:text-slate-400">
        Attention data is not available for this prediction.
      </div>
    )
  }

  return (
    <div
      role="img"
      aria-label="Parameter influence heatmap. Higher values mean the parameter influenced the decision more."
      className="space-y-2"
    >
      {sorted.map((w) => {
        const pct = (w.weight / max) * 100
        const label = (LAB_REFERENCE as Record<string, { label: string } | undefined>)[w.param]?.label ?? String(w.param)
        const intensity = Math.min(100, Math.max(15, pct))
        return (
          <div key={w.param} className="flex items-center gap-3">
            <div className="w-28 flex-shrink-0 text-sm font-medium text-slate-700 dark:text-slate-200 truncate">
              {label}
            </div>
            <div
              className="h-3 flex-1 rounded-full bg-slate-100 dark:bg-slate-700 overflow-hidden"
              aria-hidden="true"
            >
              <div
                className="h-full rounded-full transition-[width] duration-500"
                style={{
                  width: `${pct}%`,
                  background: `linear-gradient(90deg, rgba(30,64,175,${intensity / 100}), rgba(239,68,68,${(intensity / 100) * 0.6}))`,
                }}
              />
            </div>
            <div className="w-12 text-right text-xs font-semibold tabular-nums text-slate-700 dark:text-slate-200">
              {formatPct(w.weight)}
            </div>
          </div>
        )
      })}
    </div>
  )
}
