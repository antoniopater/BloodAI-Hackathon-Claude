import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Camera, Upload, FileText, ArrowRight, RotateCcw } from 'lucide-react'
import { ProgressStepper } from '../Layout/ProgressStepper'
import { Card } from '../UI/Card'
import { Button } from '../UI/Button'
import { Spinner } from '../UI/Spinner'
import { EmptyState } from '../UI/EmptyState'
import { Disclaimer } from '../UI/Disclaimer'
import { CameraCapture, isCameraSupported } from '../UI/CameraCapture'
import { useOpusVision } from '../../hooks/useOpusVision'
import { useAppStore } from '../../store/useAppStore'
import { toast } from '../../store/useToastStore'
import { LAB_REFERENCE } from '../../utils/constants'
import { classifyValue, statusLabel } from '../../utils/formatters'
import { Badge, statusToTone } from '../UI/Badge'
import type { LabParam } from '../../types/medical'

export function ScanScreen() {
  const fileRef = useRef<HTMLInputElement>(null)
  const cameraRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)
  const [cameraOpen, setCameraOpen] = useState(false)
  const { run, loading, error, result, previewUrl, reset } = useOpusVision()
  const navigate = useNavigate()
  const mergeLabValues = useAppStore((s) => s.mergeLabValues)
  const setInput = useAppStore((s) => s.setInput)

  const handleFile = async (file: File) => {
    if (!file) return
    if (file.size > 12 * 1024 * 1024) {
      toast.error('File is larger than 12 MB. Please choose a smaller image or PDF.')
      return
    }
    const resp = await run(file)
    if (resp) {
      mergeLabValues(resp.values)
      if (resp.collectedAt) setInput({ collectedAt: resp.collectedAt })
      toast.success('We extracted your values. Please review them.', 'Scan complete')
    }
  }

  const onPickFile = () => fileRef.current?.click()

  // Prefer the live webcam / rear-cam stream. Fall back to the native file
  // picker (with `capture="environment"`) when getUserMedia isn't available —
  // that still launches the camera app on legacy mobile browsers.
  const onTakePhoto = () => {
    if (isCameraSupported()) {
      setCameraOpen(true)
    } else {
      cameraRef.current?.click()
    }
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) void handleFile(file)
  }

  return (
    <div className="space-y-6">
      <ProgressStepper current={1} />

      <header>
        <h1 className="text-3xl font-extrabold text-slate-900 dark:text-slate-50">
          📷 Scan your blood test
        </h1>
        <p className="mt-2 text-base text-slate-700 dark:text-slate-200">
          Take a photo or upload a PDF. We'll recognize the values and let you review them before
          analysis.
        </p>
      </header>

      {error && (
        <div
          role="alert"
          className="rounded-xl border border-danger-500/40 bg-danger-50 p-4 text-sm text-danger-700 dark:bg-danger-700/20 dark:text-danger-500"
        >
          <strong>We couldn't read the image.</strong> {error.message}{' '}
          <button
            type="button"
            className="ml-2 underline font-semibold"
            onClick={() => navigate('/input')}
          >
            Enter manually instead
          </button>
        </div>
      )}

      {!result && !loading && (
        <Card padding="lg">
          <div
            onDragOver={(e) => {
              e.preventDefault()
              setDragOver(true)
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            className={
              'flex flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed p-8 text-center ' +
              (dragOver
                ? 'border-primary-700 bg-primary-50 dark:bg-primary-800/30'
                : 'border-slate-300 bg-slate-50 dark:border-slate-600 dark:bg-slate-800/40')
            }
            aria-label="Drop zone for blood test images or PDF"
          >
            <div className="rounded-full bg-white p-4 text-primary-700 card-shadow dark:bg-slate-700 dark:text-primary-100" aria-hidden="true">
              <Upload className="h-8 w-8" />
            </div>
            <div>
              <p className="text-lg font-bold text-slate-900 dark:text-slate-50">
                Take a photo or choose a file
              </p>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
                JPG, PNG or PDF. Max 12 MB. Nothing leaves your browser until you click analyze.
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-3 pt-2">
              <Button
                size="lg"
                leftIcon={<Camera className="h-5 w-5" aria-hidden="true" />}
                onClick={onTakePhoto}
              >
                Take photo
              </Button>
              <Button
                size="lg"
                variant="secondary"
                leftIcon={<FileText className="h-5 w-5" aria-hidden="true" />}
                onClick={onPickFile}
              >
                Choose file
              </Button>
            </div>
            <input
              ref={cameraRef}
              type="file"
              accept="image/*"
              capture="environment"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) void handleFile(f)
                e.target.value = ''
              }}
            />
            <input
              ref={fileRef}
              type="file"
              accept="image/*,application/pdf"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) void handleFile(f)
                e.target.value = ''
              }}
            />
          </div>

          <p className="mt-4 text-center text-sm text-slate-500 dark:text-slate-400">
            Prefer typing?{' '}
            <button
              type="button"
              className="font-semibold text-primary-800 hover:underline dark:text-primary-100"
              onClick={() => navigate('/input')}
            >
              Enter values manually
            </button>
          </p>
        </Card>
      )}

      {loading && (
        <Card padding="lg">
          <div className="flex flex-col items-center gap-4 py-10 text-center">
            <Spinner size="lg" label="Scanning card" />
            <p className="text-lg font-semibold text-slate-800 dark:text-slate-100">
              Scanning your card…
            </p>
            <p className="text-sm text-slate-600 dark:text-slate-300">
              Opus Vision is reading the values. This usually takes a few seconds.
            </p>
            {previewUrl && (
              <img
                src={previewUrl}
                alt="Preview of the uploaded blood test"
                className="mt-4 max-h-64 rounded-xl border border-slate-200 dark:border-slate-700"
              />
            )}
          </div>
        </Card>
      )}

      {result && !loading && (
        <Card
          padding="lg"
          title="We recognized the following values"
          description="Please double-check them before analysis. Values that look off are flagged."
          titleSlot={
            <Button
              variant="ghost"
              size="md"
              leftIcon={<RotateCcw className="h-4 w-4" aria-hidden="true" />}
              onClick={reset}
              aria-label="Scan a different image"
            >
              Scan again
            </Button>
          }
        >
          {previewUrl && (
            <div className="mb-4">
              <img
                src={previewUrl}
                alt="Scanned lab sheet preview"
                className="max-h-48 rounded-xl border border-slate-200 dark:border-slate-700"
              />
            </div>
          )}

          <ul className="grid gap-2 sm:grid-cols-2">
            {Object.entries(result.values).map(([param, value]) => {
              const p = param as LabParam
              const ref = LAB_REFERENCE[p]
              if (!ref) return null
              const status = classifyValue(p, value ?? null)
              const conf = result.confidence[p]
              return (
                <li
                  key={param}
                  className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/60"
                >
                  <div>
                    <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                      {ref.label}
                    </p>
                    <p className="text-lg font-bold text-slate-900 dark:text-slate-50">
                      {value} <span className="text-sm font-normal">{ref.unit}</span>
                    </p>
                    {conf != null && (
                      <p className="text-xs text-slate-500">
                        Confidence: {Math.round(conf * 100)}%
                      </p>
                    )}
                  </div>
                  <Badge tone={statusToTone(status)}>{statusLabel(status)}</Badge>
                </li>
              )
            })}
          </ul>

          {Object.keys(result.values).length === 0 ? (
            <EmptyState
              className="mt-6"
              title="No values detected"
              description="We couldn't find any recognisable values in the image. You can enter them manually."
              action={
                <Button onClick={() => navigate('/input')}>Enter values manually</Button>
              }
            />
          ) : (
            <div className="mt-6 flex flex-wrap justify-between gap-3">
              <Button variant="secondary" onClick={() => navigate('/input')}>
                Edit values
              </Button>
              <Button
                size="lg"
                rightIcon={<ArrowRight className="h-5 w-5" aria-hidden="true" />}
                onClick={() => navigate('/input')}
              >
                Continue
              </Button>
            </div>
          )}
        </Card>
      )}

      <Disclaimer />

      <CameraCapture
        open={cameraOpen}
        onClose={() => setCameraOpen(false)}
        onCapture={(file) => {
          setCameraOpen(false)
          void handleFile(file)
        }}
      />
    </div>
  )
}
