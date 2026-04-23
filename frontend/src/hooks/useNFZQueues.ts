import { useCallback, useEffect, useState } from 'react'
import { fetchNFZQueues } from '../services/nfzClient'
import { fetchDoctors } from '../services/nfzClient'
import { toApiError } from '../services/apiClient'
import type {
  ApiError,
  DoctorsRequest,
  DoctorsResponse,
  NFZQueuesRequest,
  NFZQueuesResponse,
} from '../types/api'

interface UseNFZQueuesResult {
  run: (req: NFZQueuesRequest) => Promise<NFZQueuesResponse | null>
  loading: boolean
  error: ApiError | null
  data: NFZQueuesResponse | null
}

export function useNFZQueues(initial?: NFZQueuesRequest): UseNFZQueuesResult {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [data, setData] = useState<NFZQueuesResponse | null>(null)

  const run = useCallback(async (req: NFZQueuesRequest) => {
    setLoading(true)
    setError(null)
    try {
      const d = await fetchNFZQueues(req)
      setData(d)
      return d
    } catch (err) {
      setError(toApiError(err))
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (initial) void run(initial)
    // only on first render with initial
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { run, loading, error, data }
}

interface UseDoctorsResult {
  run: (req?: DoctorsRequest) => Promise<DoctorsResponse | null>
  loading: boolean
  error: ApiError | null
  data: DoctorsResponse | null
}

export function useDoctors(initial?: DoctorsRequest): UseDoctorsResult {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [data, setData] = useState<DoctorsResponse | null>(null)

  const run = useCallback(async (req?: DoctorsRequest) => {
    setLoading(true)
    setError(null)
    try {
      const d = await fetchDoctors(req)
      setData(d)
      return d
    } catch (err) {
      setError(toApiError(err))
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (initial) void run(initial)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { run, loading, error, data }
}
