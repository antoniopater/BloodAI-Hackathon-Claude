import { useCallback, useState } from 'react'
import { scanImage } from '../services/opusClient'
import { toApiError } from '../services/apiClient'
import type { ScanResponse } from '../types/api'
import type { ApiError } from '../types/api'

interface UseOpusVisionResult {
  run: (file: File, hint?: string) => Promise<ScanResponse | null>
  loading: boolean
  error: ApiError | null
  result: ScanResponse | null
  previewUrl: string | null
  reset: () => void
}

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const v = reader.result
      if (typeof v === 'string') resolve(v)
      else reject(new Error('Could not read file as data URL'))
    }
    reader.onerror = () => reject(reader.error ?? new Error('File read error'))
    reader.readAsDataURL(file)
  })
}

export function useOpusVision(): UseOpusVisionResult {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [result, setResult] = useState<ScanResponse | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)

  const run = useCallback(async (file: File, hint?: string) => {
    setLoading(true)
    setError(null)
    try {
      const dataUrl = await fileToDataUrl(file)
      setPreviewUrl(dataUrl)
      const resp = await scanImage({ imageDataUrl: dataUrl, hint })
      setResult(resp)
      return resp
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
    setPreviewUrl(null)
  }, [])

  return { run, loading, error, result, previewUrl, reset }
}
