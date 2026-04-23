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

export type ThemePref = 'light' | 'dark' | 'system'
export type DisplayMode = 'patient' | 'clinical'

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
  setSelectedSpecialty: (c: TriageClass | null) => void
  setSelectedProvince: (code: string) => void
  setSelectedCity: (city: string) => void
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
      resetInput: () => set({ input: emptyPatientInput(), triage: null, explanation: null }),
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

      setSelectedSpecialty: (c) => set({ selectedSpecialty: c }),
      setSelectedProvince: (code) => set({ selectedProvince: code }),
      setSelectedCity: (city) => set({ selectedCity: city }),
    }),
    {
      name: 'bloodai-store',
      partialize: (s) => ({
        theme: s.theme,
        mode: s.mode,
        history: s.history,
        selectedProvince: s.selectedProvince,
        selectedCity: s.selectedCity,
      }),
    },
  ),
)
