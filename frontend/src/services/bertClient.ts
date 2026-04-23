import { api } from './apiClient'
import type { PredictRequest, PredictResponse } from '../types/api'

/** POST /api/predict — runs the BERT triage model and returns 8 class probabilities. */
export async function predictTriage(req: PredictRequest): Promise<PredictResponse> {
  const { data } = await api.post<PredictResponse>('/predict', req)
  return data
}
