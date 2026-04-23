import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowDown, ArrowUp, Minus, Sparkles, Trash2 } from 'lucide-react'
import { Card } from '../UI/Card'
import { Button } from '../UI/Button'
import { Select } from '../UI/Select'
import { Spinner } from '../UI/Spinner'
import { EmptyState } from '../UI/EmptyState'
import { Disclaimer } from '../UI/Disclaimer'
import { Badge } from '../UI/Badge'
import { TrendChart } from '../Medical/TrendChart'
import { useAppStore } from '../../store/useAppStore'
import { useTrendAnalysis } from '../../hooks/useTrendAnalysis'
import { LAB_PARAMS, type LabParam } from '../../types/medical'
import { LAB_REFERENCE } from '../../utils/constants'
import { formatDate, formatSignedPct } from '../../utils/formatters'

function changePct(prev: number | null, curr: number | null): number | null {
  if (prev == null || curr == null || prev === 0) return null
  return ((curr - prev) / prev) * 100
}

export function TrendsScreen() {
  const history = useAppStore((s) => s.history)
  const clearHistory = useAppStore((s) => s.clearHistory)
  const removeHistoryEntry = useAppStore((s) => s.removeHistoryEntry)
  const [selectedParam, setSelectedParam] = useState<LabParam>('HGB')
  const { run: runTrend, loading, result } = useTrendAnalysis()

  const chronologic = useMemo(
    () => [...history].sort((a, b) => a.createdAt.localeCompare(b.createdAt)),
    [history],
  )

  useEffect(() => {
    if (chronologic.length >= 2) {
      void runTrend(chronologic.map((h) => h.input))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chronologic.length])

  if (history.length === 0) {
    return (
      <div className="space-y-6">
        <header>
          <h1 className="text-3xl font-extrabold text-slate-900 dark:text-slate-50">
            📈 Your trends
          </h1>
          <p className="mt-2 text-base text-slate-700 dark:text-slate-200">
            Save at least two analyses to compare results over time.
          </p>
        </header>
        <EmptyState
          title="No history yet"
          description="Run an analysis first — each result you view is automatically saved here."
          action={
            <Link to="/input">
              <Button>Enter first result</Button>
            </Link>
          }
        />
        <Disclaimer />
      </div>
    )
  }

  const latest = chronologic[chronologic.length - 1]
  const previous = chronologic.length >= 2 ? chronologic[chronologic.length - 2] : null

  const rows = LAB_PARAMS.map((p) => {
    const curr = latest.input.values[p] ?? null
    const prev = previous?.input.values[p] ?? null
    const pct = changePct(prev, curr)
    let direction: 'up' | 'down' | 'flat' = 'flat'
    if (pct != null && Math.abs(pct) >= 1) direction = pct > 0 ? 'up' : 'down'
    return { param: p, prev, curr, pct, direction }
  }).filter((r) => r.curr != null || r.prev != null)

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 dark:text-slate-50">
            📈 Your trends
          </h1>
          <p className="mt-1 text-base text-slate-700 dark:text-slate-200">
            {chronologic.length} saved result{chronologic.length === 1 ? '' : 's'}.
            {previous &&
              ` Comparing ${formatDate(previous.createdAt)} → ${formatDate(latest.createdAt)}.`}
          </p>
        </div>
        <Button
          variant="ghost"
          leftIcon={<Trash2 className="h-4 w-4" aria-hidden="true" />}
          onClick={() => {
            if (confirm('Clear your saved history?')) clearHistory()
          }}
        >
          Clear history
        </Button>
      </header>

      {result && (
        <Card
          padding="lg"
          title={
            <span className="inline-flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary-700 dark:text-primary-100" aria-hidden="true" />
              Opus interpretation
            </span>
          }
          titleSlot={
            <Badge
              tone={
                result.urgency === 'high'
                  ? 'danger'
                  : result.urgency === 'medium'
                    ? 'warning'
                    : 'success'
              }
            >
              Urgency: {result.urgency}
            </Badge>
          }
        >
          <p className="whitespace-pre-wrap text-base leading-relaxed text-slate-800 dark:text-slate-100">
            {result.interpretation}
          </p>
        </Card>
      )}

      {loading && !result && (
        <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
          <Spinner />
          <span className="text-sm text-slate-700 dark:text-slate-200">
            Analyzing your trends…
          </span>
        </div>
      )}

      {previous && (
        <Card padding="lg" title="What changed" description={`${formatDate(previous.createdAt)} → ${formatDate(latest.createdAt)}`}>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-700" aria-label="Change table">
              <thead>
                <tr className="text-left text-sm font-semibold text-slate-600 dark:text-slate-300">
                  <th className="px-3 py-2">Parameter</th>
                  <th className="px-3 py-2">Previous</th>
                  <th className="px-3 py-2">Latest</th>
                  <th className="px-3 py-2">Change</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {rows.map((r) => {
                  const ref = LAB_REFERENCE[r.param]
                  const arrow =
                    r.direction === 'up'
                      ? <ArrowUp className="h-4 w-4" aria-hidden="true" />
                      : r.direction === 'down'
                        ? <ArrowDown className="h-4 w-4" aria-hidden="true" />
                        : <Minus className="h-4 w-4" aria-hidden="true" />
                  const arrowLabel =
                    r.direction === 'up' ? 'increase' : r.direction === 'down' ? 'decrease' : 'no change'
                  const tone =
                    r.direction === 'flat'
                      ? 'neutral'
                      : Math.abs(r.pct ?? 0) > 15
                        ? 'warning'
                        : 'info'
                  return (
                    <tr key={r.param} className="text-sm text-slate-800 dark:text-slate-100">
                      <td className="px-3 py-3 font-semibold">{ref.label}</td>
                      <td className="px-3 py-3 tabular-nums">
                        {r.prev == null ? '—' : `${r.prev} ${ref.unit}`}
                      </td>
                      <td className="px-3 py-3 tabular-nums">
                        {r.curr == null ? '—' : `${r.curr} ${ref.unit}`}
                      </td>
                      <td className="px-3 py-3">
                        <Badge tone={tone} aria-label={arrowLabel}>
                          {arrow} {formatSignedPct(r.pct)}
                        </Badge>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Card padding="lg" title="Chart" description="Pick a parameter to visualize over time.">
        <div className="mb-4 max-w-xs">
          <Select
            label="Parameter"
            value={selectedParam}
            onChange={(e) => setSelectedParam(e.target.value as LabParam)}
            options={LAB_PARAMS.map((p) => ({ value: p, label: LAB_REFERENCE[p].label }))}
          />
        </div>
        <TrendChart history={chronologic} param={selectedParam} />
      </Card>

      <Card padding="lg" title="History">
        <ul className="divide-y divide-slate-100 dark:divide-slate-700">
          {[...chronologic].reverse().map((h) => {
            const filled = Object.values(h.input.values).filter((v) => v != null).length
            return (
              <li key={h.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div>
                  <p className="font-semibold text-slate-900 dark:text-slate-50">
                    {formatDate(h.createdAt)}
                  </p>
                  <p className="text-sm text-slate-600 dark:text-slate-300">
                    {filled} value{filled === 1 ? '' : 's'} · age {h.input.age}, {h.input.sex}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="md"
                  leftIcon={<Trash2 className="h-4 w-4" aria-hidden="true" />}
                  onClick={() => removeHistoryEntry(h.id)}
                  aria-label={`Delete entry from ${formatDate(h.createdAt)}`}
                >
                  Delete
                </Button>
              </li>
            )
          })}
        </ul>
      </Card>

      <Disclaimer />
    </div>
  )
}
