import { useMemo } from 'react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  ReferenceArea,
} from 'recharts'
import type { HistoryEntry, LabParam } from '../../types/medical'
import { LAB_REFERENCE } from '../../utils/constants'
import { formatDate } from '../../utils/formatters'

interface TrendChartProps {
  history: HistoryEntry[]
  param: LabParam
  height?: number
}

export function TrendChart({ history, param, height = 280 }: TrendChartProps) {
  const ref = LAB_REFERENCE[param]

  const data = useMemo(() => {
    return [...history]
      .filter((h) => h.input.values[param] != null)
      .sort((a, b) => a.createdAt.localeCompare(b.createdAt))
      .map((h) => ({
        date: formatDate(h.createdAt),
        value: h.input.values[param] as number,
      }))
  }, [history, param])

  if (data.length < 2) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-800/40 dark:text-slate-300">
        At least two entries with a value for {ref.label} are needed to show a trend.
      </div>
    )
  }

  const values = data.map((d) => d.value)
  const dataMin = Math.min(...values, ref.low)
  const dataMax = Math.max(...values, ref.high)
  const pad = (dataMax - dataMin) * 0.15 || 1
  return (
    <div role="img" aria-label={`Trend chart of ${ref.label} over time.`}>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 10, right: 20, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-slate-200 dark:stroke-slate-700" />
          <XAxis dataKey="date" className="text-xs" />
          <YAxis
            domain={[dataMin - pad, dataMax + pad]}
            label={{ value: ref.unit, angle: -90, position: 'insideLeft', dy: 30, offset: 10 }}
          />
          <ReferenceArea y1={ref.low} y2={ref.high} strokeOpacity={0.1} fill="#10B981" fillOpacity={0.1} />
          <Tooltip
            contentStyle={{ borderRadius: 8, borderColor: '#E5E7EB' }}
            formatter={(v: number) => [`${v} ${ref.unit}`, ref.label]}
          />
          <Legend />
          <Line
            type="monotone"
            dataKey="value"
            name={ref.label}
            stroke="#1E40AF"
            strokeWidth={3}
            dot={{ r: 5, strokeWidth: 2 }}
            activeDot={{ r: 7 }}
          />
        </LineChart>
      </ResponsiveContainer>
      <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
        Green band = reference range ({ref.low}–{ref.high} {ref.unit}).
      </p>
    </div>
  )
}
