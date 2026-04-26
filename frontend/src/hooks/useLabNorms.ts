import { useEffect } from 'react'
import { api } from '../services/apiClient'
import { useAppStore } from '../store/useAppStore'
import type { LabParam, Sex } from '../types/medical'

export interface NormRange {
  low: number
  high: number
  unit: string
}

export type AgeGroup = 'kids' | 'under_30' | 'under_60' | 'seniors'

export type LabNormsByParam = {
  [param: string]: {
    [group in AgeGroup]?: {
      m?: NormRange
      f?: NormRange
    }
  }
}

export function ageToGroup(age: number): AgeGroup {
  if (age < 18) return 'kids'
  if (age < 30) return 'under_30'
  if (age < 60) return 'under_60'
  return 'seniors'
}

function sexToKey(sex: Sex | string): 'm' | 'f' {
  const s = String(sex).toLowerCase()
  return s === 'male' || s === 'm' ? 'm' : 'f'
}

/**
 * Returns the normal range for a parameter based on patient age and sex.
 * Falls back to `null` when the param is missing from the loaded norms.
 */
export function getRangeForPatient(
  param: LabParam | string,
  age: number,
  sex: Sex | string,
  labNorms?: LabNormsByParam | null,
): NormRange | null {
  if (!labNorms) return null
  const paramNorms = labNorms[param]
  if (!paramNorms) return null
  const group = ageToGroup(age)
  const groupNorms = paramNorms[group]
  if (!groupNorms) return null
  const range = groupNorms[sexToKey(sex)]
  return range ?? null
}

export function isValueInRange(value: number, range: NormRange | null): boolean {
  if (!range) return true
  return value >= range.low && value <= range.high
}

/** Fetches `/lab_norms` once and caches the result in the Zustand store. */
export function useLabNorms(): LabNormsByParam | null {
  const labNorms = useAppStore((s) => s.labNorms)
  const setLabNorms = useAppStore((s) => s.setLabNorms)

  useEffect(() => {
    if (labNorms) return
    let cancelled = false
    const fetchNorms = async () => {
      try {
        const { data } = await api.get<LabNormsByParam>('/lab_norms')
        if (!cancelled && data) setLabNorms(data)
      } catch (error) {
        console.warn('Failed to load lab norms:', error)
      }
    }
    fetchNorms()
    return () => {
      cancelled = true
    }
  }, [labNorms, setLabNorms])

  return labNorms
}
