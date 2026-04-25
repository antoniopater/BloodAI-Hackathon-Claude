import { useNavigate } from 'react-router-dom'
import { History, Trash2, RotateCcw } from 'lucide-react'
import { Card } from '../UI/Card'
import { Button } from '../UI/Button'
import { Badge } from '../UI/Badge'
import { EmptyState } from '../UI/EmptyState'
import { Disclaimer } from '../UI/Disclaimer'
import { useAppStore } from '../../store/useAppStore'
import { formatDate } from '../../utils/formatters'
import { LAB_REFERENCE } from '../../utils/constants'
import type { HistoryEntry, LabParam } from '../../types/medical'

const SUMMARY_PARAMS: LabParam[] = ['HGB', 'CREATININE', 'WBC']

export function HistoryScreen() {
  const navigate = useNavigate()
  const user = useAppStore((s) => s.user)
  const history = useAppStore((s) => s.history)
  const clearHistory = useAppStore((s) => s.clearHistory)
  const removeHistoryEntry = useAppStore((s) => s.removeHistoryEntry)
  const setInput = useAppStore((s) => s.setInput)
  const setTriage = useAppStore((s) => s.setTriage)
  const setExplanation = useAppStore((s) => s.setExplanation)

  if (!user) {
    navigate('/login', { replace: true, state: { from: '/history' } })
    return null
  }

  const restoreEntry = (entry: HistoryEntry) => {
    setInput(entry.input)
    setTriage(entry.result ?? null)
    setExplanation(entry.explanation ?? null)
    navigate('/triage')
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 dark:text-slate-50">
            📋 My History
          </h1>
          <p className="mt-1 text-base text-slate-600 dark:text-slate-300">
            {history.length} saved result{history.length !== 1 ? 's' : ''} for {user.name}
          </p>
        </div>
        {history.length > 0 && (
          <Button
            variant="danger"
            size="md"
            leftIcon={<Trash2 className="h-4 w-4" />}
            onClick={() => { if (window.confirm('Clear all saved results?')) clearHistory() }}
          >
            Clear all
          </Button>
        )}
      </header>

      {history.length === 0 ? (
        <EmptyState
          icon={<History className="h-6 w-6" />}
          title="No history yet"
          description="Run your first analysis — results are saved here automatically."
          action={<Button onClick={() => navigate('/input')}>Enter results</Button>}
        />
      ) : (
        <div className="space-y-4">
          {history.map((entry) => (
            <HistoryCard
              key={entry.id}
              entry={entry}
              onRestore={() => restoreEntry(entry)}
              onRemove={() => removeHistoryEntry(entry.id)}
            />
          ))}
        </div>
      )}

      <Disclaimer />
    </div>
  )
}

function HistoryCard({
  entry,
  onRestore,
  onRemove,
}: {
  entry: HistoryEntry
  onRestore: () => void
  onRemove: () => void
}) {
  const topClass = entry.result?.predictions
    ? [...entry.result.predictions].sort((a, b) => b.probability - a.probability)[0]?.class
    : null

  return (
    <Card padding="md" className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0 space-y-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-base font-bold text-slate-900 dark:text-slate-50">
            {formatDate(entry.createdAt)}
          </span>
          {topClass && <Badge tone="info">{topClass}</Badge>}
          <span className="text-sm text-slate-500 dark:text-slate-400">
            Age {entry.input.age} · {entry.input.sex}
          </span>
        </div>
        <div className="flex flex-wrap gap-4">
          {SUMMARY_PARAMS.map((p) => {
            const val = entry.input.values[p]
            if (val == null) return null
            const ref = LAB_REFERENCE[p]
            return (
              <span key={p} className="text-sm text-slate-700 dark:text-slate-200">
                {ref.label}: <strong>{val}</strong>{' '}
                <span className="text-xs text-slate-500 dark:text-slate-400">{ref.unit}</span>
              </span>
            )
          })}
        </div>
      </div>
      <div className="flex flex-shrink-0 gap-2">
        <Button
          variant="secondary"
          size="md"
          leftIcon={<RotateCcw className="h-4 w-4" />}
          onClick={onRestore}
        >
          Restore
        </Button>
        <Button
          variant="ghost"
          size="md"
          onClick={onRemove}
          aria-label="Remove this entry"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    </Card>
  )
}
