import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, FlaskConical, RotateCcw, Sparkles } from 'lucide-react'
import { ProgressStepper } from '../Layout/ProgressStepper'
import { Card } from '../UI/Card'
import { Button } from '../UI/Button'
import { Input } from '../UI/Input'
import { Select } from '../UI/Select'
import { Disclaimer } from '../UI/Disclaimer'
import { Spinner } from '../UI/Spinner'
import { ParameterExplainer } from '../Medical/ParameterExplainer'
import { useAppStore } from '../../store/useAppStore'
import { useBertTriage } from '../../hooks/useBertTriage'
import { LAB_PARAMS } from '../../types/medical'
import type { LabParam, PatientInput } from '../../types/medical'
import { validatePatientInput, parseNumber } from '../../utils/validators'
import { toast } from '../../store/useToastStore'

const TEST_PRESETS: { label: string; emoji: string; data: Partial<PatientInput> & { values: Record<string, number> } }[] = [
  {
    label: 'Healthy',
    emoji: '✅',
    data: {
      age: 32, sex: 'female',
      values: { HGB: 13.5, HCT: 40, PLT: 230, MCV: 88, WBC: 6.2, CREATININE: 0.8, ALT: 22, AST: 18, UREA: 14 },
    },
  },
  {
    label: 'Anemia',
    emoji: '🩸',
    data: {
      age: 28, sex: 'female',
      values: { HGB: 9.2, HCT: 28, PLT: 210, MCV: 72, WBC: 5.8, CREATININE: 0.7, ALT: 18, AST: 16, UREA: 12 },
    },
  },
  {
    label: 'Kidney',
    emoji: '🫘',
    data: {
      age: 58, sex: 'male',
      values: { HGB: 11.0, HCT: 33, PLT: 180, MCV: 84, WBC: 7.1, CREATININE: 3.2, ALT: 28, AST: 30, UREA: 42 },
    },
  },
  {
    label: 'Liver',
    emoji: '🟤',
    data: {
      age: 45, sex: 'male',
      values: { HGB: 12.8, HCT: 38, PLT: 95, MCV: 96, WBC: 8.4, CREATININE: 1.0, ALT: 210, AST: 185, UREA: 18 },
    },
  },
  {
    label: 'Urgent ER',
    emoji: '🚨',
    data: {
      age: 70, sex: 'male',
      values: { HGB: 7.1, HCT: 22, PLT: 38, MCV: 78, WBC: 18.5, CREATININE: 5.8, ALT: 95, AST: 120, UREA: 68 },
    },
  },
]

export function InputScreen() {
  const navigate = useNavigate()
  const input = useAppStore((s) => s.input)
  const setInput = useAppStore((s) => s.setInput)
  const setLabValue = useAppStore((s) => s.setLabValue)
  const resetInput = useAppStore((s) => s.resetInput)
  const mergeLabValues = useAppStore((s) => s.mergeLabValues)
  const setTriage = useAppStore((s) => s.setTriage)
  const setExplanation = useAppStore((s) => s.setExplanation)
  const saveCurrentToHistory = useAppStore((s) => s.saveCurrentToHistory)
  const user = useAppStore((s) => s.user)

  const { run: runTriage, loading: loadingTriage } = useBertTriage()

  const [errors, setErrors] = useState<Record<string, string>>({})

  const hasValues = useMemo(
    () => Object.values(input.values).some((v) => v != null),
    [input.values],
  )

  const loadPreset = (preset: typeof TEST_PRESETS[number]) => {
    setInput({ age: preset.data.age, sex: preset.data.sex as 'male' | 'female' })
    mergeLabValues(preset.data.values as Partial<Record<LabParam, number>>)
    setErrors({})
  }

  const handleAnalyze = async () => {
    const errs = validatePatientInput(input)
    setErrors(errs)
    if (Object.keys(errs).length > 0) {
      toast.error('Please fix the highlighted fields.', 'Some fields need attention')
      return
    }
    const result = await runTriage(input)
    if (!result) {
      toast.error('We could not reach the triage service. Please try again.', 'Analysis failed')
      return
    }
    setTriage(result)
    setExplanation(null)
    if (user) {
      saveCurrentToHistory()
    } else {
      toast.info('Create an account to save this result and track your history.', 'Results not saved')
    }
    navigate('/triage')
  }

  return (
    <div className="space-y-6">
      <ProgressStepper current={2} />

      <header>
        <h1 className="text-3xl font-extrabold text-slate-900 dark:text-slate-50">
          📝 Enter your results
        </h1>
        <p className="mt-2 text-base text-slate-700 dark:text-slate-200">
          Fill in the values from your lab report. Hover the <strong>?</strong> next to each name
          for a plain-language explanation.
        </p>
      </header>

      <Card padding="md">
        <div className="flex flex-wrap items-center gap-2">
          <span className="flex items-center gap-1 text-sm font-semibold text-slate-500 dark:text-slate-400">
            <FlaskConical className="h-4 w-4" aria-hidden="true" />
            Test presets:
          </span>
          {TEST_PRESETS.map((preset) => (
            <button
              key={preset.label}
              type="button"
              onClick={() => loadPreset(preset)}
              className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:border-primary-400 hover:bg-primary-50 hover:text-primary-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:border-primary-500 dark:hover:bg-primary-900/30"
            >
              <span aria-hidden="true">{preset.emoji}</span>
              {preset.label}
            </button>
          ))}
        </div>
      </Card>

      <Card padding="lg" title="About you" description="These two fields help us personalise the analysis.">
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Age"
            type="number"
            inputMode="numeric"
            min={0}
            max={120}
            step={1}
            value={input.age ?? ''}
            onChange={(e) => setInput({ age: parseNumber(e.target.value) ?? 0 })}
            error={errors.age}
            hint="Your age in years."
          />
          <Select
            label="Sex"
            value={input.sex}
            onChange={(e) => setInput({ sex: e.target.value as 'male' | 'female' })}
            options={[
              { value: 'female', label: 'Female' },
              { value: 'male', label: 'Male' },
            ]}
            error={errors.sex}
          />
        </div>
      </Card>

      <Card
        padding="lg"
        title="Lab values"
        description="Enter what you have — you don't need to fill every field."
        titleSlot={
          <Button
            variant="ghost"
            size="md"
            leftIcon={<RotateCcw className="h-4 w-4" aria-hidden="true" />}
            onClick={resetInput}
            aria-label="Reset all lab values"
          >
            Reset
          </Button>
        }
      >
        {errors.values && (
          <div
            role="alert"
            className="mb-4 rounded-xl border border-warning-500/50 bg-warning-50 p-3 text-sm text-warning-700 dark:bg-warning-700/20"
          >
            {errors.values}
          </div>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          {LAB_PARAMS.map((p) => (
            <ParameterExplainer
              key={p}
              param={p}
              value={input.values[p]}
              onChange={(v) => setLabValue(p, v)}
              error={errors[`values.${p}`]}
            />
          ))}
        </div>
      </Card>

      <Card padding="md">
        <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-sm text-slate-600 dark:text-slate-300">
            {hasValues ? 'Ready when you are.' : 'Enter at least one lab value to continue.'}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => navigate('/scan')}>
              Back to scan
            </Button>
            <Button
              size="xl"
              loading={loadingTriage}
              onClick={handleAnalyze}
              disabled={!hasValues}
              rightIcon={
                loadingTriage ? null : <ArrowRight className="h-5 w-5" aria-hidden="true" />
              }
              leftIcon={
                !loadingTriage ? <Sparkles className="h-5 w-5" aria-hidden="true" /> : null
              }
              aria-label="Analyze results"
            >
              {loadingTriage ? 'Analyzing…' : 'Analyze Results'}
            </Button>
          </div>
        </div>
        {loadingTriage && (
          <div className="mt-4 flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
            <Spinner size="sm" />
            Running BERT triage model…
          </div>
        )}
      </Card>

      <Disclaimer />
    </div>
  )
}
