import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type {
  HistoryEntry,
  LabParam,
  OpusExplanation,
  PatientInput,
  TriageResult,
} from '../types/medical'
import type { TriageClass } from '../types/medical'
import { LAB_PARAMS } from '../types/medical'
import { shortId } from '../utils/formatters'
import type { LabNormsByParam } from '../hooks/useLabNorms'

export type ThemePref = 'light' | 'dark' | 'system'
export type DisplayMode = 'patient' | 'clinical'

export interface GeoCoords {
  lat: number
  lng: number
}

/** Province centroids (approximate) for auto-detection from GPS coords. */
const PROVINCE_CENTROIDS: Array<{ code: string; lat: number; lng: number }> = [
  { code: '01', lat: 51.1, lng: 16.2 },
  { code: '02', lat: 53.2, lng: 18.7 },
  { code: '03', lat: 51.2, lng: 23.0 },
  { code: '04', lat: 52.2, lng: 15.2 },
  { code: '05', lat: 51.8, lng: 19.5 },
  { code: '06', lat: 49.9, lng: 20.1 },
  { code: '07', lat: 52.3, lng: 21.0 },
  { code: '08', lat: 50.6, lng: 17.9 },
  { code: '09', lat: 49.9, lng: 22.3 },
  { code: '10', lat: 53.1, lng: 22.9 },
  { code: '11', lat: 54.2, lng: 18.1 },
  { code: '12', lat: 50.3, lng: 18.7 },
  { code: '13', lat: 50.6, lng: 20.9 },
  { code: '14', lat: 53.8, lng: 20.9 },
  { code: '15', lat: 52.2, lng: 17.7 },
  { code: '16', lat: 53.5, lng: 15.5 },
]

export function guessProvinceFromCoords(lat: number, lng: number): string {
  let bestCode = '07'
  let bestDist = Infinity
  for (const c of PROVINCE_CENTROIDS) {
    const d = Math.hypot(lat - c.lat, lng - c.lng)
    if (d < bestDist) { bestDist = d; bestCode = c.code }
  }
  return bestCode
}

function emptyValues(): Record<LabParam, number | null> {
  return Object.fromEntries(LAB_PARAMS.map((p) => [p, null])) as Record<LabParam, number | null>
}

export function emptyPatientInput(): PatientInput {
  return {
    age: 45,
    sex: 'female',
    values: emptyValues(),
  }
}

interface AppState {
  theme: ThemePref
  mode: DisplayMode
  input: PatientInput
  triage: TriageResult | null
  explanation: OpusExplanation | null
  history: HistoryEntry[]
  /** Specialty selected for Doctor Finder (from triage). */
  selectedSpecialty: TriageClass | null
  selectedProvince: string
  selectedCity: string
  symptomTokens: string[]

  setTheme: (t: ThemePref) => void
  setMode: (m: DisplayMode) => void
  setInput: (partial: Partial<PatientInput>) => void
  setLabValue: (param: LabParam, value: number | null) => void
  mergeLabValues: (values: Partial<Record<LabParam, number>>) => void
  resetInput: () => void
  setTriage: (t: TriageResult | null) => void
  setExplanation: (e: OpusExplanation | null) => void
  saveCurrentToHistory: () => void
  clearHistory: () => void
  removeHistoryEntry: (id: string) => void
  /** Seeds 4 demo sessions showing CKD progression — for hackathon demo. */
  seedDemoHistory: () => void
  setSelectedSpecialty: (c: TriageClass | null) => void
  setSelectedProvince: (code: string) => void
  setSelectedCity: (city: string) => void
  setSymptomTokens: (tokens: string[]) => void
  clearSymptomTokens: () => void

  /** Age/sex-stratified lab reference ranges fetched from backend `/lab_norms`. */
  labNorms: LabNormsByParam | null
  setLabNorms: (norms: LabNormsByParam) => void

  user: { name: string; email: string } | null
  login: (name: string, email: string) => void
  logout: () => void

  /** User's GPS position (null = not yet granted or not asked). */
  userLocation: GeoCoords | null
  setUserLocation: (loc: GeoCoords | null) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      theme: 'system',
      mode: 'patient',
      input: emptyPatientInput(),
      triage: null,
      explanation: null,
      history: [],
      selectedSpecialty: null,
      selectedProvince: '07',
      selectedCity: '',
      symptomTokens: [],

      setTheme: (t) => set({ theme: t }),
      setMode: (m) => set({ mode: m }),
      setInput: (partial) => set((s) => ({ input: { ...s.input, ...partial } })),
      setLabValue: (param, value) =>
        set((s) => ({ input: { ...s.input, values: { ...s.input.values, [param]: value } } })),
      mergeLabValues: (values) =>
        set((s) => ({
          input: {
            ...s.input,
            values: {
              ...s.input.values,
              ...Object.fromEntries(
                Object.entries(values).filter(([, v]) => v != null),
              ),
            },
          },
        })),
      resetInput: () => set({ input: emptyPatientInput(), triage: null, explanation: null, symptomTokens: [] }),
      setSymptomTokens: (tokens) => set({ symptomTokens: tokens }),
      clearSymptomTokens: () => set({ symptomTokens: [] }),
      setTriage: (t) => set({ triage: t }),
      setExplanation: (e) => set({ explanation: e }),

      saveCurrentToHistory: () => {
        const { input, triage, explanation } = get()
        const entry: HistoryEntry = {
          id: shortId(),
          createdAt: new Date().toISOString(),
          input: { ...input, values: { ...input.values } },
          result: triage ?? undefined,
          explanation: explanation ?? undefined,
        }
        set((s) => ({ history: [entry, ...s.history].slice(0, 20) }))
      },
      clearHistory: () => set({ history: [] }),
      removeHistoryEntry: (id) =>
        set((s) => ({ history: s.history.filter((h) => h.id !== id) })),

      seedDemoHistory: () => {
        const base: Array<{ daysAgo: number; values: Record<LabParam, number> }> = [
          {
            daysAgo: 168,
            values: { HGB: 14.0, CREATININE: 1.0, PLT: 250, MCV: 88, WBC: 6.5, ALT: 22, AST: 24, UREA: 14 },
          },
          {
            daysAgo: 96,
            values: { HGB: 12.0, CREATININE: 1.8, PLT: 240, MCV: 87, WBC: 6.8, ALT: 25, AST: 26, UREA: 22 },
          },
          {
            daysAgo: 42,
            values: { HGB: 10.5, CREATININE: 2.5, PLT: 220, MCV: 86, WBC: 7.0, ALT: 27, AST: 28, UREA: 30 },
          },
          {
            daysAgo: 0,
            values: { HGB: 8.5, CREATININE: 3.2, PLT: 200, MCV: 85, WBC: 7.2, ALT: 30, AST: 30, UREA: 38 },
          },
        ]
        const now = Date.now()
        const entries: HistoryEntry[] = base.map((row) => {
          const ts = new Date(now - row.daysAgo * 86400000).toISOString()
          return {
            id: shortId(),
            createdAt: ts,
            input: {
              age: 45,
              sex: 'female',
              values: { ...row.values } as Record<LabParam, number | null>,
              collectedAt: ts,
            },
          }
        })
        // newest first (matches existing convention)
        set({ history: [...entries].reverse() })
      },

      setSelectedSpecialty: (c) => set({ selectedSpecialty: c }),
      setSelectedProvince: (code) => set({ selectedProvince: code }),
      setSelectedCity: (city) => set({ selectedCity: city }),

      labNorms: null,
      setLabNorms: (norms) => set({ labNorms: norms }),

      user: null,
      login: (name, email) => set({ user: { name, email } }),
      logout: () => set({ user: null }),

      userLocation: null,
      setUserLocation: (loc) => set({ userLocation: loc }),
    }),
    {
      name: 'bloodai-store',
      partialize: (s) => ({
        theme: s.theme,
        mode: s.mode,
        history: s.history,
        selectedProvince: s.selectedProvince,
        selectedCity: s.selectedCity,
        user: s.user,
      }),
    },
  ),
)
