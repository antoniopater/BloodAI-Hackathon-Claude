import { useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, CheckCircle2, FlaskConical, HelpCircle, RotateCcw, Sparkles, XCircle } from 'lucide-react'
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
import type { AdaptiveQuestion } from '../../types/api'
import { computeTriggers } from '../../services/bertClient'
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
  const setSymptomTokens = useAppStore((s) => s.setSymptomTokens)
  const user = useAppStore((s) => s.user)

  const { run: runTriage, loading: loadingTriage } = useBertTriage()

  const [errors, setErrors] = useState<Record<string, string>>({})
  const [questions, setQuestions] = useState<AdaptiveQuestion[]>([])
  const [answers, setAnswers] = useState<Record<string, boolean | null>>({})
  const [loadingQuestions, setLoadingQuestions] = useState(false)
  const [showQuestions, setShowQuestions] = useState(false)
  const questionsRef = useRef<HTMLDivElement>(null)

  const hasValues = useMemo(
    () => Object.values(input.values).some((v) => v != null),
    [input.values],
  )

  const loadPreset = (preset: typeof TEST_PRESETS[number]) => {
    setInput({ age: preset.data.age, sex: preset.data.sex as 'male' | 'female' })
    mergeLabValues(preset.data.values as Partial<Record<LabParam, number>>)
    setErrors({})
    setQuestions([])
    setAnswers({})
    setShowQuestions(false)
  }

  function collectSymptomTokens(): string[] {
    return questions
      .map((q) => {
        const answered = answers[q.intent]
        if (answered === true) return q.token_yes
        if (answered === false) return q.token_no
        return null
      })
      .filter((t): t is string => t != null)
  }

  async function runFinalAnalysis(tokens: string[]) {
    setSymptomTokens(tokens)
    const result = await runTriage(input, tokens.length > 0 ? tokens : undefined)
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

  const handleAnalyze = async () => {
    const errs = validatePatientInput(input)
    setErrors(errs)
    if (Object.keys(errs).length > 0) {
      toast.error('Please fix the highlighted fields.', 'Some fields need attention')
      return
    }

    if (showQuestions) {
      await runFinalAnalysis(collectSymptomTokens())
      return
    }

    // Phase 1: fetch adaptive questions based on flagged values
    setLoadingQuestions(true)
    try {
      const result = await computeTriggers({ age: input.age, sex: input.sex, values: input.values })
      if (result.questions.length > 0) {
        setQuestions(result.questions)
        setAnswers({})
        setShowQuestions(true)
        setTimeout(() => questionsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
        return
      }
    } catch {
      // compute_triggers unavailable → proceed without questions
    } finally {
      setLoadingQuestions(false)
    }

    await runFinalAnalysis([])
  }

  const handleSkipQuestions = () => runFinalAnalysis([])

  const isLoading = loadingTriage || loadingQuestions

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
              age={input.age}
              sex={input.sex}
            />
          ))}
        </div>
      </Card>

      {/* Adaptive questions — shown after phase-1 trigger analysis */}
      {showQuestions && questions.length > 0 && (
        <div ref={questionsRef}>
          <Card
            padding="lg"
            title="A few quick questions"
            description="Your results flagged some values. These help the model give a more accurate referral."
          >
            <div className="space-y-4">
              {questions.map((q, i) => {
                const answered = answers[q.intent]
                return (
                  <div
                    key={i}
                    className="flex flex-col gap-2 rounded-xl border border-slate-200 p-4 dark:border-slate-700"
                  >
                    <p className="flex items-start gap-2 text-sm font-medium text-slate-800 dark:text-slate-100">
                      <HelpCircle className="mt-0.5 h-4 w-4 shrink-0 text-primary-500" aria-hidden="true" />
                      {q.text}
                    </p>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setAnswers((prev) => ({ ...prev, [q.intent]: true }))}
                        className={`flex items-center gap-1.5 rounded-lg border px-4 py-2 text-sm font-semibold transition ${
                          answered === true
                            ? 'border-green-500 bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                            : 'border-slate-200 bg-slate-50 text-slate-600 hover:border-green-400 hover:bg-green-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300'
                        }`}
                      >
                        <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                        Yes
                      </button>
                      <button
                        type="button"
                        onClick={() => setAnswers((prev) => ({ ...prev, [q.intent]: false }))}
                        className={`flex items-center gap-1.5 rounded-lg border px-4 py-2 text-sm font-semibold transition ${
                          answered === false
                            ? 'border-red-400 bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                            : 'border-slate-200 bg-slate-50 text-slate-600 hover:border-red-400 hover:bg-red-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300'
                        }`}
                      >
                        <XCircle className="h-4 w-4" aria-hidden="true" />
                        No
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          </Card>
        </div>
      )}

      <Card padding="md">
        <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-sm text-slate-600 dark:text-slate-300">
            {showQuestions
              ? `${Object.keys(answers).length} of ${questions.length} questions answered.`
              : hasValues
              ? 'Ready when you are.'
              : 'Enter at least one lab value to continue.'}
          </div>
          <div className="flex flex-wrap gap-2">
            {showQuestions ? (
              <>
                <Button
                  variant="secondary"
                  onClick={handleSkipQuestions}
                  disabled={loadingTriage}
                >
                  Skip questions
                </Button>
                <Button
                  size="xl"
                  loading={loadingTriage}
                  onClick={handleAnalyze}
                  rightIcon={loadingTriage ? null : <ArrowRight className="h-5 w-5" aria-hidden="true" />}
                  leftIcon={!loadingTriage ? <Sparkles className="h-5 w-5" aria-hidden="true" /> : null}
                >
                  {loadingTriage ? 'Analyzing…' : 'Analyze with My Answers'}
                </Button>
              </>
            ) : (
              <>
                <Button variant="secondary" onClick={() => navigate('/scan')}>
                  Back to scan
                </Button>
                <Button
                  size="xl"
                  loading={isLoading}
                  onClick={handleAnalyze}
                  disabled={!hasValues}
                  rightIcon={isLoading ? null : <ArrowRight className="h-5 w-5" aria-hidden="true" />}
                  leftIcon={!isLoading ? <Sparkles className="h-5 w-5" aria-hidden="true" /> : null}
                  aria-label="Analyze results"
                >
                  {loadingQuestions ? 'Checking values…' : loadingTriage ? 'Analyzing…' : 'Analyze Results'}
                </Button>
              </>
            )}
          </div>
        </div>
        {isLoading && (
          <div className="mt-4 flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
            <Spinner size="sm" />
            {loadingQuestions ? 'Looking for relevant questions…' : 'Running BERT triage model…'}
          </div>
        )}
      </Card>

      <Disclaimer />
    </div>
  )
}
