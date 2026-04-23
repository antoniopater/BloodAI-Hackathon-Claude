import type { TriageClass } from './medical'

export type DoctorSource = 'nfz' | 'private'

export interface Doctor {
  id: string
  source: DoctorSource
  name: string
  specialty: string
  /** Canonical triage class this specialty maps to, if any. */
  triageClass?: TriageClass
  address: string
  city: string
  province: string
  phone?: string
  bookingUrl?: string
  /** Distance from the user, km. Optional. */
  distanceKm?: number
  /** Rating 0..5 (private only). */
  rating?: number
  reviewCount?: number
  /** Typical price per visit in PLN (private only). */
  pricePln?: number
  /** Days until the first available appointment. */
  waitDays?: number
  /** Next available date (ISO). */
  nextAvailable?: string
  lat?: number
  lng?: number
}

export interface NFZQueueEntry {
  /** Clinic / provider name. */
  provider: string
  address: string
  city: string
  province: string
  phone?: string
  /** ISO date string of the first available appointment. */
  firstAvailable: string | null
  waitDays: number | null
  lat?: number
  lng?: number
}

export type DoctorSortBy = 'wait' | 'distance' | 'rating'
