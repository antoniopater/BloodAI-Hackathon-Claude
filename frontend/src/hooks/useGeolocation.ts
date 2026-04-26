import { useCallback, useRef, useState } from 'react'

export interface GeoCoords {
  lat: number
  lng: number
}

export type GeoStatus = 'idle' | 'loading' | 'granted' | 'denied' | 'unsupported'

interface UseGeolocationReturn {
  status: GeoStatus
  coords: GeoCoords | null
  error: string | null
  request: () => void
}

export function useGeolocation(): UseGeolocationReturn {
  const [status, setStatus] = useState<GeoStatus>('idle')
  const [coords, setCoords] = useState<GeoCoords | null>(null)
  const [error, setError] = useState<string | null>(null)
  const didRequest = useRef(false)

  const request = useCallback(() => {
    if (didRequest.current) return
    didRequest.current = true

    if (!navigator.geolocation) {
      setStatus('unsupported')
      setError('Geolocation is not supported by your browser.')
      return
    }

    setStatus('loading')
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude })
        setStatus('granted')
        setError(null)
      },
      (err) => {
        setStatus('denied')
        setError(
          err.code === err.PERMISSION_DENIED
            ? 'Location access was denied.'
            : err.code === err.TIMEOUT
              ? 'Location request timed out.'
              : 'Could not determine your location.',
        )
      },
      { timeout: 10_000, maximumAge: 5 * 60_000 },
    )
  }, [])

  return { status, coords, error, request }
}
