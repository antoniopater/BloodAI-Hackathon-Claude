import type { LabParam, Sex } from '../../types/medical'
import { LAB_REFERENCE } from '../../utils/constants'
import { classifyValue, statusLabel, statusAria } from '../../utils/formatters'
import { Badge, statusToTone } from '../UI/Badge'
import { Input } from '../UI/Input'
import { Tooltip } from '../UI/Tooltip'
import { parseNumber } from '../../utils/validators'
import { getRangeForPatient, useLabNorms } from '../../hooks/useLabNorms'

interface ParameterExplainerProps {
  param: LabParam
  value: number | null
  onChange: (value: number | null) => void
  error?: string | null
  age: number
  sex: Sex
}

export function ParameterExplainer({ param, value, onChange, error, age, sex }: ParameterExplainerProps) {
  const labNorms = useLabNorms()
  const ref = LAB_REFERENCE[param]
  const dynamicRange = getRangeForPatient(param, age, sex, labNorms)
  const low = dynamicRange?.low ?? ref.low
  const high = dynamicRange?.high ?? ref.high
  const unit = dynamicRange?.unit ?? ref.unit

  const status = classifyValue(param, value, dynamicRange)
  const tone = statusToTone(status)

  const helpContent = (
    <div className="space-y-1">
      <p className="font-semibold">
        {ref.label} ({unit})
      </p>
      <p>{ref.description}</p>
      <p className="mt-1 opacity-80">
        Normal: {low}–{high} {unit}
      </p>
      {dynamicRange && (
        <p className="text-xs opacity-70">
          Tailored for age {age}, {sex === 'male' ? 'male' : 'female'}.
        </p>
      )}
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
        placeholder={`${low}–${high}`}
        value={value ?? ''}
        onChange={(e) => onChange(parseNumber(e.target.value))}
        suffix={<span className="text-slate-500">{unit}</span>}
        hint={`Normal range: ${low}–${high} ${unit}`}
        error={error}
      />
    </div>
  )
}
