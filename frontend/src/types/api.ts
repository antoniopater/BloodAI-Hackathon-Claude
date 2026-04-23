import type {
  LabParam,
  OpusExplanation,
  PatientInput,
  TrendAnalysis,
  TriageResult,
} from './medical'
import type { Doctor, NFZQueueEntry } from './doctor'

// ---- POST /api/predict --------------------------------------------------
export interface PredictRequest {
  input: PatientInput
}

export interface PredictResponse extends TriageResult {}

// ---- POST /api/scan -----------------------------------------------------
/** The image is sent as base64 data-URL. Backend decodes + forwards to Opus Vision. */
export interface ScanRequest {
  imageDataUrl: string
  /** Optional hint: which lab issued the report (helps OCR). */
  hint?: string
}

export interface ScanResponse {
  values: Partial<Record<LabParam, number>>
  /** Confidence per detected value, 0..1. */
  confidence: Partial<Record<LabParam, number>>
  /** Raw OCR text (for debugging / clinical mode). */
  rawText?: string
  /** Detected collection date, ISO. */
  collectedAt?: string
}

// ---- POST /api/explain --------------------------------------------------
export interface ExplainRequest {
  input: PatientInput
  triage?: TriageResult
  mode: 'patient' | 'clinical'
}

export interface ExplainResponse extends OpusExplanation {}

// ---- POST /api/trends ---------------------------------------------------
export interface TrendsRequest {
  history: PatientInput[]
}

export interface TrendsResponse extends TrendAnalysis {}

// ---- GET /api/nfz/queues ------------------------------------------------
export interface NFZQueuesRequest {
  benefit: string // e.g. "PORADNIA NEFROLOGICZNA"
  province: string // e.g. "07"
  case: 1 | 2
}

export interface NFZQueuesResponse {
  entries: NFZQueueEntry[]
}

// ---- GET /api/doctors ---------------------------------------------------
export interface DoctorsRequest {
  specialty?: string
  city?: string
  province?: string
}

export interface DoctorsResponse {
  doctors: Doctor[]
}

// ---- generic ------------------------------------------------------------
export interface ApiError {
  message: string
  code?: string
  status?: number
}
