import axios, { AxiosError, AxiosInstance } from 'axios'
import type { ApiError } from '../types/api'

const baseURL =
  (import.meta.env && (import.meta.env.VITE_API_BASE_URL as string)) || '/api'

export const api: AxiosInstance = axios.create({
  baseURL,
  timeout: 60_000,
  headers: {
    'Content-Type': 'application/json',
  },
})

/** Convert an axios error into a predictable ApiError. */
export function toApiError(err: unknown): ApiError {
  if (axios.isAxiosError(err)) {
    const axErr = err as AxiosError<{ message?: string; detail?: string }>
    const data = axErr.response?.data
    const message =
      data?.message ??
      data?.detail ??
      axErr.message ??
      'Something went wrong contacting the server.'
    return {
      message,
      code: axErr.code,
      status: axErr.response?.status,
    }
  }
  if (err instanceof Error) return { message: err.message }
  return { message: 'Unknown error' }
}
