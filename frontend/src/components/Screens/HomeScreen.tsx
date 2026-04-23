import { Link } from 'react-router-dom'
import { Camera, ClipboardList, LineChart, MapPin, Stethoscope, Sparkles } from 'lucide-react'
import { Button } from '../UI/Button'
import { Disclaimer } from '../UI/Disclaimer'
import { useAppStore } from '../../store/useAppStore'

export function HomeScreen() {
  const historyCount = useAppStore((s) => s.history.length)

  return (
    <div className="space-y-10">
      <section className="grid gap-8 md:grid-cols-2 md:items-center">
        <div>
          <span className="inline-flex items-center gap-1 rounded-full bg-primary-50 px-3 py-1 text-sm font-semibold text-primary-800 dark:bg-primary-800/30 dark:text-primary-100">
            <Sparkles className="h-4 w-4" aria-hidden="true" /> Powered by Claude Opus 4.7
          </span>
          <h1 className="mt-3 text-3xl sm:text-4xl font-extrabold leading-tight text-slate-900 dark:text-slate-50">
            Understand your blood test results —<br />
            <span className="text-primary-800 dark:text-primary-100">in plain language.</span>
          </h1>
          <p className="mt-4 text-base sm:text-lg text-slate-700 dark:text-slate-200">
            Scan or type your results. We'll explain what they mean and suggest which specialist to
            see, with real NFZ appointment waiting times.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Button
              size="xl"
              onClick={() => (window.location.href = '/scan')}
              leftIcon={<Camera className="h-5 w-5" aria-hidden="true" />}
            >
              Scan a result
            </Button>
            <Link to="/input" className="inline-flex">
              <Button
                size="xl"
                variant="secondary"
                leftIcon={<ClipboardList className="h-5 w-5" aria-hidden="true" />}
              >
                Enter manually
              </Button>
            </Link>
          </div>
          {historyCount > 0 && (
            <p className="mt-4 text-sm text-slate-600 dark:text-slate-300">
              You have {historyCount} saved result{historyCount === 1 ? '' : 's'}.{' '}
              <Link to="/trends" className="font-semibold text-primary-800 hover:underline dark:text-primary-100">
                See your trends →
              </Link>
            </p>
          )}
        </div>
        <div className="rounded-3xl border border-slate-200 bg-white p-6 card-shadow-lg dark:border-slate-700 dark:bg-slate-800">
          <Stepline />
        </div>
      </section>

      <Disclaimer />

      <section aria-labelledby="features-heading">
        <h2 id="features-heading" className="sr-only">
          Features
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Feature
            icon={<Camera className="h-6 w-6" />}
            title="Scan on the go"
            description="Take a photo of a lab report — we extract values automatically."
          />
          <Feature
            icon={<Stethoscope className="h-6 w-6" />}
            title="8-way triage"
            description="A medical-grade BERT model points to the right specialist."
          />
          <Feature
            icon={<LineChart className="h-6 w-6" />}
            title="Track trends"
            description="Compare multiple results and spot rapid changes early."
          />
          <Feature
            icon={<MapPin className="h-6 w-6" />}
            title="Find a doctor"
            description="See NFZ waiting times and private clinics — all on one map."
          />
        </div>
      </section>
    </div>
  )
}

function Feature({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode
  title: string
  description: string
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 card-shadow dark:border-slate-700 dark:bg-slate-800">
      <div className="inline-flex h-11 w-11 items-center justify-center rounded-lg bg-primary-50 text-primary-800 dark:bg-primary-800/30 dark:text-primary-100">
        {icon}
      </div>
      <h3 className="mt-3 text-lg font-bold text-slate-900 dark:text-slate-50">{title}</h3>
      <p className="mt-1 text-sm text-slate-700 dark:text-slate-200">{description}</p>
    </div>
  )
}

function Stepline() {
  const items = [
    { icon: <Camera className="h-5 w-5" />, title: '1. Scan your lab sheet', desc: 'Camera, PDF, or type values manually.' },
    { icon: <Stethoscope className="h-5 w-5" />, title: '2. Get a triage', desc: 'See which specialists fit your results.' },
    { icon: <MapPin className="h-5 w-5" />, title: '3. Find a doctor', desc: 'Compare NFZ waits and private options.' },
  ]
  return (
    <ol className="space-y-4">
      {items.map((it) => (
        <li key={it.title} className="flex items-start gap-4">
          <div className="mt-1 inline-flex h-10 w-10 items-center justify-center rounded-full bg-primary-700 text-white" aria-hidden="true">
            {it.icon}
          </div>
          <div>
            <p className="text-base font-bold text-slate-900 dark:text-slate-50">{it.title}</p>
            <p className="text-sm text-slate-700 dark:text-slate-200">{it.desc}</p>
          </div>
        </li>
      ))}
    </ol>
  )
}
