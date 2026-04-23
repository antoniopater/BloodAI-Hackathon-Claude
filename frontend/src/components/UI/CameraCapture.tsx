import { useCallback, useEffect, useRef, useState } from 'react'
import { Camera, RefreshCcw, X, AlertCircle } from 'lucide-react'
import { Modal } from './Modal'
import { Button } from './Button'
import { Spinner } from './Spinner'

/**
 * Live camera capture that works on both laptop (webcam) and phone (rear camera).
 *
 * Uses `navigator.mediaDevices.getUserMedia` — requires HTTPS or localhost
 * (Vite dev satisfies the second). When the API isn't available or permission
 * is denied, an inline error suggests the file-upload path instead; callers
 * should keep their file-picker fallback wired.
 */
interface CameraCaptureProps {
  open: boolean
  onClose: () => void
  onCapture: (file: File) => void
}

type Facing = 'environment' | 'user'

export function isCameraSupported(): boolean {
  return typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices &&
    typeof navigator.mediaDevices.getUserMedia === 'function'
}

export function CameraCapture({ open, onClose, onCapture }: CameraCaptureProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [facing, setFacing] = useState<Facing>('environment')
  const [busy, setBusy] = useState(false)

  const stopStream = useCallback(() => {
    const s = streamRef.current
    if (s) {
      s.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    if (videoRef.current) {
      try {
        videoRef.current.srcObject = null
      } catch {
        /* ignore */
      }
    }
  }, [])

  useEffect(() => {
    if (!open) return
    let cancelled = false
    setReady(false)
    setError(null)

    const start = async () => {
      if (!isCameraSupported()) {
        setError('Your browser does not support live camera access. Use "Choose file" instead.')
        return
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: { ideal: facing },
            width: { ideal: 1920 },
            height: { ideal: 1080 },
          },
          audio: false,
        })
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }
        streamRef.current = stream
        const v = videoRef.current
        if (v) {
          v.srcObject = stream
          // Required attrs for iOS Safari inline playback.
          v.setAttribute('playsinline', 'true')
          v.muted = true
          try {
            await v.play()
          } catch {
            /* Safari sometimes rejects autoplay; the stream is still live. */
          }
          setReady(true)
        }
      } catch (err) {
        const name = (err as DOMException).name
        if (name === 'NotAllowedError' || name === 'SecurityError') {
          setError('Camera access was blocked. Allow it in your browser settings and try again.')
        } else if (name === 'NotFoundError' || name === 'OverconstrainedError') {
          setError('No suitable camera was found on this device.')
        } else {
          setError((err as Error).message || 'Could not start the camera.')
        }
      }
    }

    void start()

    return () => {
      cancelled = true
      stopStream()
    }
  }, [open, facing, stopStream])

  // Stop the stream when the dialog closes for any reason.
  useEffect(() => {
    if (!open) stopStream()
  }, [open, stopStream])

  const switchCamera = useCallback(() => {
    setFacing((f) => (f === 'environment' ? 'user' : 'environment'))
  }, [])

  const capture = useCallback(async () => {
    const v = videoRef.current
    if (!v || !ready) return
    setBusy(true)
    try {
      const w = v.videoWidth || 1280
      const h = v.videoHeight || 720
      const canvas = document.createElement('canvas')
      canvas.width = w
      canvas.height = h
      const ctx = canvas.getContext('2d')
      if (!ctx) {
        setError('Could not access the canvas to capture the frame.')
        return
      }
      ctx.drawImage(v, 0, 0, w, h)
      const blob: Blob | null = await new Promise((resolve) =>
        canvas.toBlob((b) => resolve(b), 'image/jpeg', 0.92),
      )
      if (!blob) {
        setError('Capture failed. Please try again.')
        return
      }
      const file = new File([blob], `scan-${Date.now()}.jpg`, { type: 'image/jpeg' })
      stopStream()
      onCapture(file)
    } finally {
      setBusy(false)
    }
  }, [ready, onCapture, stopStream])

  const close = useCallback(() => {
    stopStream()
    onClose()
  }, [stopStream, onClose])

  return (
    <Modal
      open={open}
      onClose={close}
      size="lg"
      title="Take a photo of your lab sheet"
      description="Hold the sheet flat, fill the frame, avoid glare. Tap Capture when it's sharp."
    >
      {error ? (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-xl border border-danger-500/40 bg-danger-50 p-4 text-sm text-danger-700 dark:bg-danger-700/20 dark:text-danger-500"
        >
          <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0" aria-hidden="true" />
          <div>
            <p className="font-semibold">Camera unavailable</p>
            <p className="mt-1">{error}</p>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="relative overflow-hidden rounded-xl bg-black">
            <video
              ref={videoRef}
              className="block w-full h-auto"
              playsInline
              muted
              autoPlay
              aria-label="Live camera preview"
            />
            {!ready && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/40 text-white">
                <Spinner size="lg" label="Starting camera" />
              </div>
            )}
            <div className="pointer-events-none absolute inset-6 rounded-xl border-2 border-dashed border-white/50" aria-hidden="true" />
          </div>

          <div className="flex flex-wrap items-center justify-center gap-3">
            <Button
              variant="secondary"
              size="md"
              leftIcon={<RefreshCcw className="h-4 w-4" aria-hidden="true" />}
              onClick={switchCamera}
              disabled={!ready}
              aria-label="Switch between front and back camera"
            >
              Switch camera
            </Button>
            <Button
              size="xl"
              leftIcon={<Camera className="h-5 w-5" aria-hidden="true" />}
              onClick={capture}
              disabled={!ready}
              loading={busy}
            >
              Capture
            </Button>
            <Button
              variant="ghost"
              size="md"
              leftIcon={<X className="h-4 w-4" aria-hidden="true" />}
              onClick={close}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}
    </Modal>
  )
}
