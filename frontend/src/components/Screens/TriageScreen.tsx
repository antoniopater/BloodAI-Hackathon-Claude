import { useEffect, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, Sparkles, Stethoscope, User } from 'lucide-react'
import { ProgressStepper } from '../Layout/ProgressStepper'
import { Card } from '../UI/Card'
import { Button } from '../UI/Button'
import { Tabs } from '../UI/Tabs'
import { Spinner } from '../UI/Spinner'
import { Badge } from '../UI/Badge'
import { Disclaimer } from '../UI/Disclaimer'
import { EmptyState } from '../UI/EmptyState'
import { TriageResults } from '../Medical/TriageResults'
import { AttentionHeatmap } from '../UI/AttentionHeatmap'
import { useAppStore } from '../../store/useAppStore'
import { useOpusExplainer } from '../../hooks/useOpusExplainer'
import type { TriagePrediction } from '../../types/medical'
import { DEFAULT_FOLLOWUP_QUESTIONS, TRIAGE_LABELS } from '../../utils/constants'
import { formatPct } from '../../utils/formatters'

export function TriageScreen() {
  const navigate = useNavigate()
  const triage = useAppStore((s) => s.triage)
  const input = useAppStore((s) => s.input)
  const mode = useAppStore((s) => s.mode)
  const setMode = useAppStore((s) => s.setMode)
  const explanation = useAppStore((s) => s.explanation)
  const setExplanation = useAppStore((s) => s.setExplanation)
  const selectedSpecialty = useAppStore((s) => s.selectedSpecialty)
  const setSelectedSpecialty = useAppStore((s) => s.setSelectedSpecialty)
  const { run: runExplainer, loading: loadingExplain, error: explainError } = useOpusExplainer()

  const topPrediction: TriagePrediction | null = useMemo(() => {
    if (!triage || triage.predictions.length === 0) return null
    return [...triage.predictions].sort((a, b) => b.probability - a.probability)[0]
  }, [triage])

  useEffect(() => {
    if (!triage) return
    if (explanation) return
    void runExplainer({ input, triage, mode }).then((resp) => {
      if (resp) setExplanation(resp)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [triage])

  useEffect(() => {
    if (!triage) return
    if (!explanation) return
    // Re-run explanation when the mode toggles, to get the correctly-toned summary.
    void runExplainer({ input, triage, mode }).then((resp) => {
      if (resp) setExplanation(resp)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode])

  useEffect(() => {
    // Pre-select the top specialty so Doctor Finder is ready to go.
    if (topPrediction && !selectedSpecialty) {
      setSelectedSpecialty(topPrediction.class)
    }
  }, [topPrediction, selectedSpecialty, setSelectedSpecialty])

  if (!triage) {
    return (
      <div className="space-y-6">
        <ProgressStepper current={3} />
        <EmptyState
          icon={<Stethoscope className="h-6 w-6" />}
          title="No analysis yet"
          description="Enter your results first — we'll show you the triage here."
          action={<Button onClick={() => navigate('/input')}>Enter results</Button>}
        />
        <Disclaimer />
      </div>
    )
  }

  const fallbackFollowUps = topPrediction
    ? DEFAULT_FOLLOWUP_QUESTIONS[topPrediction.class] ?? []
    : []
  const followUps = explanation?.followUpQuestions?.length
    ? explanation.followUpQuestions
    : fallbackFollowUps

  const goDoctors = () => {
    if (topPrediction) setSelectedSpecialty(selectedSpecialty ?? topPrediction.class)
    navigate('/doctors')
  }

  return (
    <div className="space-y-6">
      <ProgressStepper current={3} />

      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 dark:text-slate-50">
            🔬 Your analysis
          </h1>
          <p className="mt-1 text-base text-slate-700 dark:text-slate-200">
            We recommend visiting these specialists, ordered by likelihood.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Tabs
            label="Display mode"
            value={mode}
            onChange={(v) => setMode(v)}
            tabs={[
              {
                id: 'patient',
                label: 'Patient',
                icon: <User className="h-4 w-4" aria-hidden="true" />,
              },
              {
                id: 'clinical',
                label: 'Clinical',
                icon: <Stethoscope className="h-4 w-4" aria-hidden="true" />,
              },
            ]}
          />
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-6 lg:col-span-3">
          <Card padding="lg" title="Recommended specialists">
            <TriageResults
              predictions={triage.predictions}
              mode={mode}
              selectedClass={selectedSpecialty}
              onSelect={(p) => setSelectedSpecialty(p.class)}
            />
            {mode === 'clinical' && triage.ece != null && (
              <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
                Calibration (ECE): {formatPct(triage.ece)} · Model {triage.modelVersion ?? 'v1'}
              </p>
            )}
          </Card>

          <Card
            padding="lg"
            title={
              <span className="inline-flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-primary-700 dark:text-primary-100" aria-hidden="true" />
                Opus explanation
              </span>
            }
            description={mode === 'patient' ? 'Plain language summary.' : 'Clinical summary.'}
          >
            {loadingExplain && !explanation ? (
              <div className="flex items-center gap-3 py-6">
                <Spinner />
                <span className="text-sm text-slate-600 dark:text-slate-300">
                  Generating explanation…
                </span>
              </div>
            ) : explainError && !explanation ? (
              <p className="text-sm text-slate-600 dark:text-slate-300">
                We couldn't reach the explainer ({explainError.message}). The triage above is still
                valid — please consult your doctor.
              </p>
            ) : explanation ? (
              <div className="space-y-3">
                <p className="whitespace-pre-wrap text-base leading-relaxed text-slate-800 dark:text-slate-100">
                  {mode === 'patient'
                    ? explanation.patientSummary
                    : (explanation.clinicalSummary ?? explanation.patientSummary)}
                </p>
                {explanation.redFlags && explanation.redFlags.length > 0 && (
                  <div className="rounded-xl border border-danger-500/30 bg-danger-50 p-3 dark:bg-danger-700/15">
                    <p className="text-sm font-bold text-danger-700 dark:text-danger-500">
                      Red flags
                    </p>
                    <ul className="mt-1 list-disc pl-5 text-sm text-slate-800 dark:text-slate-100">
                      {explanation.redFlags.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-slate-600 dark:text-slate-300">
                Generating a plain-language summary…
              </p>
            )}
          </Card>

          {followUps.length > 0 && (
            <Card padding="lg" title="A few follow-up questions" description="These help refine the recommendation.">
              <ul className="space-y-2">
                {followUps.map((q, i) => (
                  <li
                    key={i}
                    className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-base text-slate-800 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100"
                  >
                    {q}
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>

        <div className="space-y-6 lg:col-span-2">
          <Card padding="lg" title="Top match">
            {topPrediction && (
              <div className="text-center">
                <div className="text-5xl" aria-hidden="true">
                  {TRIAGE_LABELS[topPrediction.class].emoji}
                </div>
                <p className="mt-2 text-xl font-bold text-slate-900 dark:text-slate-50">
                  {mode === 'patient'
                    ? TRIAGE_LABELS[topPrediction.class].patient
                    : TRIAGE_LABELS[topPrediction.class].en}
                </p>
                <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
                  {formatPct(topPrediction.probability)} likelihood
                </p>
                <Button size="xl" fullWidth className="mt-5" onClick={goDoctors} rightIcon={<ArrowRight className="h-5 w-5" aria-hidden="true" />}>
                  Find Doctor
                </Button>
              </div>
            )}
          </Card>

          {mode === 'clinical' && (
            <Card padding="lg" title="Attention heatmap" description="Which parameters influenced the decision.">
              <AttentionHeatmap weights={triage.attention} />
            </Card>
          )}

          <Card padding="md">
            <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
              Next step
            </p>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
              Save to history?{' '}
              <Link
                to="/trends"
                className="font-semibold text-primary-800 hover:underline dark:text-primary-100"
              >
                View your trends →
              </Link>
            </p>
            {mode === 'clinical' && (
              <div className="mt-3 flex flex-wrap gap-2">
                <Badge tone="info">patient-level split 80/20</Badge>
                <Badge tone="info">focal γ-loss</Badge>
                <Badge tone="info">8 classes</Badge>
              </div>
            )}
          </Card>
        </div>
      </div>

      <Disclaimer />
    </div>
  )
}
