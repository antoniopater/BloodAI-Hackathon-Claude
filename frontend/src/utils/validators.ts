import { z } from 'zod'
import { LAB_PARAMS } from '../types/medical'

const labValueSchema = z
  .union([z.number().min(0).max(10000), z.null()])
  .optional()
  .transform((v) => (v === undefined ? null : v))

// Build a zod object shape from LAB_PARAMS without exceeding TS's readonly-tuple handling.
const valuesShape: Record<string, typeof labValueSchema> = {}
for (const p of LAB_PARAMS) valuesShape[p] = labValueSchema

export const patientInputSchema = z.object({
  age: z.number().int().min(0).max(120),
  sex: z.enum(['male', 'female']),
  values: z.object(valuesShape),
  notes: z.string().max(2000).optional(),
  collectedAt: z.string().optional(),
})

export type PatientInputSchema = z.infer<typeof patientInputSchema>

/** Returns a record of per-field error messages (empty object = valid). */
export function validatePatientInput(
  input: Partial<{
    age: number | null | string
    sex: 'male' | 'female' | null
    values: Record<string, number | null>
  }>,
): Record<string, string> {
  const errors: Record<string, string> = {}
  const ageNum = typeof input.age === 'string' ? Number(input.age) : input.age
  if (ageNum == null || Number.isNaN(ageNum)) errors.age = 'Enter your age.'
  else if (ageNum < 0 || ageNum > 120) errors.age = 'Age must be between 0 and 120.'

  if (input.sex !== 'male' && input.sex !== 'female') errors.sex = 'Select your sex.'

  const values = input.values ?? {}
  const filled = Object.values(values).filter((v) => v != null && !Number.isNaN(v)).length
  if (filled === 0) errors.values = 'Enter at least one lab value.'

  for (const p of LAB_PARAMS) {
    const v = values[p]
    if (v == null) continue
    if (typeof v !== 'number' || Number.isNaN(v)) {
      errors[`values.${p}`] = 'Enter a number.'
      continue
    }
    if (v < 0 || v > 10000) {
      errors[`values.${p}`] = 'Value looks unrealistic.'
    }
  }
  return errors
}

/** Parse a user-typed number, accepting either comma or dot decimal separator. */
export function parseNumber(input: string): number | null {
  if (!input.trim()) return null
  const normalized = input.replace(',', '.').trim()
  const n = Number(normalized)
  return Number.isFinite(n) ? n : null
}
