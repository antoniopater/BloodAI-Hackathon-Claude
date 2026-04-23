import { Camera, ClipboardList, Stethoscope, MapPin, Check } from 'lucide-react'
import { cn } from '../../utils/cn'
import { TOTAL_STEPS } from '../../utils/constants'

export type StepId = 1 | 2 | 3 | 4

interface StepMeta {
  id: StepId
  label: string
  icon: React.ReactNode
}

const steps: StepMeta[] = [
  { id: 1, label: 'Scan', icon: <Camera className="h-5 w-5" aria-hidden="true" /> },
  { id: 2, label: 'Enter', icon: <ClipboardList className="h-5 w-5" aria-hidden="true" /> },
  { id: 3, label: 'Triage', icon: <Stethoscope className="h-5 w-5" aria-hidden="true" /> },
  { id: 4, label: 'Doctors', icon: <MapPin className="h-5 w-5" aria-hidden="true" /> },
]

interface ProgressStepperProps {
  current: StepId
  className?: string
}

export function ProgressStepper({ current, className }: ProgressStepperProps) {
  return (
    <div
      className={cn('w-full', className)}
      role="progressbar"
      aria-valuemin={1}
      aria-valuemax={TOTAL_STEPS}
      aria-valuenow={current}
      aria-label={`Step ${current} of ${TOTAL_STEPS}`}
    >
      <ol className="flex items-center justify-between gap-2">
        {steps.map((step, idx) => {
          const status: 'done' | 'current' | 'upcoming' =
            step.id < current ? 'done' : step.id === current ? 'current' : 'upcoming'
          return (
            <li key={step.id} className="flex flex-1 items-center">
              <div className="flex flex-col items-center gap-1 flex-shrink-0">
                <div
                  className={cn(
                    'flex h-10 w-10 items-center justify-center rounded-full border-2 font-bold',
                    status === 'done' && 'bg-success-500 border-success-500 text-white',
                    status === 'current' && 'bg-primary-700 border-primary-700 text-white',
                    status === 'upcoming' && 'bg-white border-slate-300 text-slate-500 dark:bg-slate-800 dark:border-slate-600',
                  )}
                  aria-current={status === 'current' ? 'step' : undefined}
                >
                  {status === 'done' ? <Check className="h-5 w-5" aria-hidden="true" /> : step.icon}
                </div>
                <span
                  className={cn(
                    'text-xs sm:text-sm font-medium',
                    status === 'current' ? 'text-primary-800 dark:text-primary-100' : 'text-slate-500 dark:text-slate-400',
                  )}
                >
                  {step.id}. {step.label}
                </span>
              </div>
              {idx < steps.length - 1 && (
                <div
                  className={cn(
                    'mx-2 h-1 flex-1 rounded-full',
                    step.id < current ? 'bg-success-500' : 'bg-slate-200 dark:bg-slate-700',
                  )}
                  aria-hidden="true"
                />
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
