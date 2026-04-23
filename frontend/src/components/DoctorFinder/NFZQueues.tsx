import type { NFZQueueEntry } from '../../types/doctor'
import { Phone, MapPin, Calendar } from 'lucide-react'
import { Badge } from '../UI/Badge'
import { formatDate, formatWaitDays } from '../../utils/formatters'

interface NFZQueuesProps {
  entries: NFZQueueEntry[]
}

export function NFZQueues({ entries }: NFZQueuesProps) {
  if (entries.length === 0) return null

  return (
    <ul className="grid gap-3" aria-label="NFZ (public) providers">
      {entries.map((e, i) => (
        <li
          key={`${e.provider}-${i}`}
          className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h4 className="truncate text-base font-bold text-slate-900 dark:text-slate-50">
                {e.provider}
              </h4>
              <p className="mt-1 flex items-center gap-1 text-sm text-slate-700 dark:text-slate-200">
                <MapPin className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
                {e.address}
                {e.city ? `, ${e.city}` : ''}
              </p>
              {e.phone && (
                <p className="mt-1 flex items-center gap-1 text-sm">
                  <Phone className="h-4 w-4 flex-shrink-0 text-slate-500" aria-hidden="true" />
                  <a
                    href={`tel:${e.phone}`}
                    className="text-primary-800 hover:underline dark:text-primary-100"
                  >
                    {e.phone}
                  </a>
                </p>
              )}
            </div>
            <Badge tone={e.waitDays != null && e.waitDays < 30 ? 'success' : 'warning'}>
              <Calendar className="h-3 w-3" aria-hidden="true" /> {formatWaitDays(e.waitDays)}
            </Badge>
          </div>
          {e.firstAvailable && (
            <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
              First available: {formatDate(e.firstAvailable)}
            </p>
          )}
        </li>
      ))}
    </ul>
  )
}
