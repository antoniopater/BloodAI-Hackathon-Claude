import { api } from './apiClient'
import type {
  ExplainRequest,
  ExplainResponse,
  ScanRequest,
  ScanResponse,
  TrendsRequest,
  TrendsResponse,
} from '../types/api'

/** POST /api/scan — extract lab values from a photo / PDF (Opus 4.7 Vision OCR). */
export async function scanImage(req: ScanRequest): Promise<ScanResponse> {
  const { data } = await api.post<ScanResponse>('/scan', req)
  return data
}

/** POST /api/explain — plain-language + clinical explanation from Opus. */
export async function explainResult(req: ExplainRequest): Promise<ExplainResponse> {
  const { data } = await api.post<ExplainResponse>('/explain', req)
  return data
}

/** POST /api/trends — compare multiple result sets and produce a readable trend. */
export async function analyzeTrends(req: TrendsRequest): Promise<TrendsResponse> {
  const { data } = await api.post<TrendsResponse>('/trends', req)
  return data
}
