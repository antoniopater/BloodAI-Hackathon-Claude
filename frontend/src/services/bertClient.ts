import { api } from './apiClient'
import type {
  PredictRequest,
  PredictResponse,
  ComputeTriggersRequest,
  ComputeTriggersResponse,
} from '../types/api'

/** POST /api/predict — runs the BERT triage model and returns 8 class probabilities. */
export async function predictTriage(req: PredictRequest): Promise<PredictResponse> {
  const { data } = await api.post<PredictResponse>('/predict', req)
  return data
}

/** POST /api/compute_triggers — returns active triggers + adaptive questions for the given input. */
export async function computeTriggers(req: ComputeTriggersRequest): Promise<ComputeTriggersResponse> {
  const { data } = await api.post<ComputeTriggersResponse>('/compute_triggers', req)
  return data
}
