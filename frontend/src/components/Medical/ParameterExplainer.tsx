import type { LabParam } from '../../types/medical'
import { LAB_REFERENCE } from '../../utils/constants'
import { classifyValue, statusLabel, statusAria } from '../../utils/formatters'
import { Badge, statusToTone } from '../UI/Badge'
import { Input } from '../UI/Input'
import { Tooltip } from '../UI/Tooltip'
import { parseNumber } from '../../utils/validators'

interface ParameterExplainerProps {
  param: LabParam
  value: number | null
  onChange: (value: number | null) => void
  error?: string | null
}

export function ParameterExplainer({ param, value, onChange, error }: ParameterExplainerProps) {
  const ref = LAB_REFERENCE[param]
  const status = classifyValue(param, value)
  const tone = statusToTone(status)

  const helpContent = (
    <div className="space-y-1">
      <p className="font-semibold">
        {ref.label} ({ref.unit})
      </p>
      <p>{ref.description}</p>
      <p className="mt-1 opacity-80">
        Normal: {ref.low}–{ref.high} {ref.unit}
      </p>
    </div>
  )

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1">
          <label
            htmlFor={`param-${param}`}
            className="text-base font-semibold text-slate-800 dark:text-slate-100"
          >
            {ref.label}
          </label>
          <Tooltip content={helpContent} label={`What is ${ref.label}?`} />
        </div>
        <Badge tone={tone} aria-label={statusAria(status)}>
          {status === 'normal' ? '✅' : status === 'critical' ? '🚨' : status === 'unknown' ? '•' : '⚠️'}{' '}
          {statusLabel(status)}
        </Badge>
      </div>

      <Input
        id={`param-${param}`}
        type="number"
        inputMode="decimal"
        step="any"
        placeholder={`${ref.low}–${ref.high}`}
        value={value ?? ''}
        onChange={(e) => onChange(parseNumber(e.target.value))}
        suffix={<span className="text-slate-500">{ref.unit}</span>}
        hint={`Normal range: ${ref.low}–${ref.high} ${ref.unit}`}
        error={error}
      />
    </div>
  )
}
