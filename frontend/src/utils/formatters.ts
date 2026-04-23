import type { LabParam, LabValue, ParameterStatus } from '../types/medical'
import { LAB_REFERENCE } from './constants'

export function classifyValue(param: LabParam, value: number | null | undefined): ParameterStatus {
  if (value == null || Number.isNaN(value)) return 'unknown'
  const ref = LAB_REFERENCE[param]
  if (ref.criticalLow != null && value <= ref.criticalLow) return 'critical'
  if (ref.criticalHigh != null && value >= ref.criticalHigh) return 'critical'
  if (value < ref.low) return 'low'
  if (value > ref.high) return 'high'
  return 'normal'
}

export function statusLabel(status: ParameterStatus): string {
  switch (status) {
    case 'normal':
      return 'Normal'
    case 'low':
      return 'Below range'
    case 'high':
      return 'Above range'
    case 'critical':
      return 'Critical'
    case 'unknown':
      return 'Not entered'
  }
}

/** Returns an accessible text descriptor for a status (for screen readers). */
export function statusAria(status: ParameterStatus): string {
  const map: Record<ParameterStatus, string> = {
    normal: 'Normal value, within the reference range',
    low: 'Below the reference range',
    high: 'Above the reference range',
    critical: 'Critical value, outside the safe range',
    unknown: 'No value entered yet',
  }
  return map[status]
}

export function formatValue(v: LabValue): string {
  if (v.value == null || Number.isNaN(v.value)) return '—'
  const ref = LAB_REFERENCE[v.param]
  const unit = v.unit ?? ref.unit
  return `${v.value} ${unit}`
}

export function formatPct(n: number): string {
  return `${Math.round(n * 100)}%`
}

export function formatSignedPct(n: number | null): string {
  if (n == null || Number.isNaN(n)) return '—'
  const rounded = Math.round(n * 10) / 10
  const sign = rounded > 0 ? '+' : ''
  return `${sign}${rounded}%`
}

export function formatDate(iso?: string): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

export function formatWaitDays(n?: number | null): string {
  if (n == null || Number.isNaN(n)) return 'Unknown'
  if (n === 0) return 'Today'
  if (n === 1) return '1 day'
  if (n < 7) return `${n} days`
  if (n < 30) return `${Math.round(n / 7)} weeks`
  return `${Math.round(n / 30)} months`
}

export function formatPricePln(n?: number): string {
  if (n == null) return '—'
  return `${n} zł`
}

/** Generates a short pseudo-unique id for local history entries. */
export function shortId(): string {
  return Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4)
}
