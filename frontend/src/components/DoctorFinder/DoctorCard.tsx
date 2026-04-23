import { Phone, MapPin, Star, Calendar, ExternalLink } from 'lucide-react'
import type { Doctor } from '../../types/doctor'
import { Badge } from '../UI/Badge'
import { Button } from '../UI/Button'
import { formatDate, formatPricePln, formatWaitDays } from '../../utils/formatters'

interface DoctorCardProps {
  doctor: Doctor
  onBook?: (doctor: Doctor) => void
}

export function DoctorCard({ doctor, onBook }: DoctorCardProps) {
  const isNFZ = doctor.source === 'nfz'
  return (
    <article
      className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5 card-shadow dark:border-slate-700 dark:bg-slate-800"
      aria-label={`${doctor.name} — ${doctor.specialty}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-lg font-bold text-slate-900 dark:text-slate-50">
            {doctor.name}
          </h3>
          <p className="text-sm text-slate-600 dark:text-slate-300">{doctor.specialty}</p>
        </div>
        <Badge tone={isNFZ ? 'info' : 'neutral'}>
          {isNFZ ? 'NFZ' : 'Private'}
        </Badge>
      </div>

      <dl className="mt-3 grid gap-2 text-sm">
        <div className="flex items-start gap-2 text-slate-700 dark:text-slate-200">
          <MapPin className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
          <span>
            {doctor.address}
            {doctor.city ? `, ${doctor.city}` : ''}
            {doctor.distanceKm != null && (
              <span className="ml-2 text-slate-500">· {doctor.distanceKm.toFixed(1)} km</span>
            )}
          </span>
        </div>

        <div className="flex items-center gap-4 text-slate-700 dark:text-slate-200">
          {doctor.waitDays != null && (
            <span className="inline-flex items-center gap-1">
              <Calendar className="h-4 w-4" aria-hidden="true" />
              <strong>{formatWaitDays(doctor.waitDays)}</strong>
              {doctor.nextAvailable && (
                <span className="text-slate-500">({formatDate(doctor.nextAvailable)})</span>
              )}
            </span>
          )}
          {!isNFZ && doctor.rating != null && (
            <span className="inline-flex items-center gap-1">
              <Star className="h-4 w-4 text-warning-500" aria-hidden="true" />
              <strong>{doctor.rating.toFixed(1)}</strong>
              {doctor.reviewCount != null && (
                <span className="text-slate-500">({doctor.reviewCount})</span>
              )}
            </span>
          )}
          {!isNFZ && doctor.pricePln != null && (
            <span className="font-semibold text-slate-900 dark:text-slate-50">
              {formatPricePln(doctor.pricePln)}
            </span>
          )}
        </div>
      </dl>

      <div className="mt-4 flex flex-wrap gap-2">
        {doctor.phone && (
          <Button
            variant="secondary"
            size="md"
            leftIcon={<Phone className="h-4 w-4" aria-hidden="true" />}
            onClick={() => {
              window.location.href = `tel:${doctor.phone}`
            }}
            aria-label={`Call ${doctor.name}`}
          >
            Call
          </Button>
        )}
        {doctor.bookingUrl ? (
          <Button
            variant="primary"
            size="md"
            rightIcon={<ExternalLink className="h-4 w-4" aria-hidden="true" />}
            onClick={() => {
              window.open(doctor.bookingUrl, '_blank', 'noopener,noreferrer')
            }}
          >
            Book appointment
          </Button>
        ) : onBook ? (
          <Button variant="primary" size="md" onClick={() => onBook(doctor)}>
            Book appointment
          </Button>
        ) : null}
      </div>
    </article>
  )
}
