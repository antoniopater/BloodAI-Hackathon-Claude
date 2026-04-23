import { api } from './apiClient'
import type {
  DoctorsRequest,
  DoctorsResponse,
  NFZQueuesRequest,
  NFZQueuesResponse,
} from '../types/api'

/** GET /api/nfz/queues — first-available appointment dates from the NFZ open API. */
export async function fetchNFZQueues(req: NFZQueuesRequest): Promise<NFZQueuesResponse> {
  const { data } = await api.get<NFZQueuesResponse>('/nfz/queues', {
    params: {
      benefit: req.benefit,
      province: req.province,
      case: req.case,
    },
  })
  return data
}

/** GET /api/doctors — private doctors (e.g. via Google Places). */
export async function fetchDoctors(req: DoctorsRequest = {}): Promise<DoctorsResponse> {
  const { data } = await api.get<DoctorsResponse>('/doctors', { params: req })
  return data
}
