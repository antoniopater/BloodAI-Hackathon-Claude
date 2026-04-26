import { useCallback, useState } from 'react'
import { predictTriage } from '../services/bertClient'
import { toApiError } from '../services/apiClient'
import type { PatientInput, TriageResult } from '../types/medical'
import type { ApiError } from '../types/api'

interface UseBertTriageResult {
  run: (input: PatientInput, symptomTokens?: string[]) => Promise<TriageResult | null>
  loading: boolean
  error: ApiError | null
  result: TriageResult | null
  reset: () => void
}

export function useBertTriage(): UseBertTriageResult {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [result, setResult] = useState<TriageResult | null>(null)

  const run = useCallback(async (input: PatientInput, symptomTokens?: string[]) => {
    setLoading(true)
    setError(null)
    try {
      const data = await predictTriage({ input, symptom_tokens: symptomTokens })
      setResult(data)
      return data
    } catch (err) {
      const e = toApiError(err)
      setError(e)
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  const reset = useCallback(() => {
    setResult(null)
    setError(null)
    setLoading(false)
  }, [])

  return { run, loading, error, result, reset }
}
