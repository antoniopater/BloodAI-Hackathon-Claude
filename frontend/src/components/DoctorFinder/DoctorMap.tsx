import { useMemo } from 'react'
import { MapContainer, Marker, Popup, TileLayer } from 'react-leaflet'
import L from 'leaflet'
import type { Doctor } from '../../types/doctor'

// Fix default icon paths (Leaflet looks for images relative to CSS which vite can't resolve).
// Point at CDN icons so marker pins show up.
const DefaultIcon = L.icon({
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
})
L.Marker.prototype.options.icon = DefaultIcon

interface DoctorMapProps {
  doctors: Doctor[]
  height?: number
  /** Fallback center when none of the doctors have coords. Defaults to Warsaw. */
  fallbackCenter?: [number, number]
}

export function DoctorMap({
  doctors,
  height = 400,
  fallbackCenter = [52.2297, 21.0122],
}: DoctorMapProps) {
  const withCoords = useMemo(
    () => doctors.filter((d) => d.lat != null && d.lng != null),
    [doctors],
  )

  const center: [number, number] = useMemo(() => {
    if (withCoords.length === 0) return fallbackCenter
    const avgLat = withCoords.reduce((s, d) => s + (d.lat as number), 0) / withCoords.length
    const avgLng = withCoords.reduce((s, d) => s + (d.lng as number), 0) / withCoords.length
    return [avgLat, avgLng]
  }, [withCoords, fallbackCenter])

  if (withCoords.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-800/40 dark:text-slate-300"
        style={{ height }}
      >
        Map locations are not available for the current results.
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-700" style={{ height }}>
      <MapContainer center={center} zoom={11} style={{ height: '100%', width: '100%' }} scrollWheelZoom>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {withCoords.map((d) => (
          <Marker key={d.id} position={[d.lat as number, d.lng as number]}>
            <Popup>
              <div className="min-w-[200px] text-sm">
                <div className="font-bold">{d.name}</div>
                <div className="text-slate-600">{d.specialty}</div>
                <div className="mt-1">{d.address}</div>
                {d.phone && (
                  <a href={`tel:${d.phone}`} className="mt-1 block text-primary-800">
                    {d.phone}
                  </a>
                )}
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  )
}
