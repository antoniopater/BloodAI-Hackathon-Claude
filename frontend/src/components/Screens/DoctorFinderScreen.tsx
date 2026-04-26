import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Filter, MapPin, Navigation, SlidersHorizontal } from 'lucide-react'
import { ProgressStepper } from '../Layout/ProgressStepper'
import { Card } from '../UI/Card'
import { Button } from '../UI/Button'
import { Select } from '../UI/Select'
import { Input } from '../UI/Input'
import { Tabs } from '../UI/Tabs'
import { Spinner } from '../UI/Spinner'
import { EmptyState } from '../UI/EmptyState'
import { Disclaimer } from '../UI/Disclaimer'
import { DoctorCard } from '../DoctorFinder/DoctorCard'
import { DoctorMap } from '../DoctorFinder/DoctorMap'
import { NFZQueues } from '../DoctorFinder/NFZQueues'
import { useAppStore, guessProvinceFromCoords } from '../../store/useAppStore'
import { useDoctors, useNFZQueues } from '../../hooks/useNFZQueues'
import { useGeolocation } from '../../hooks/useGeolocation'
import { PL_PROVINCES, TRIAGE_LABELS, TRIAGE_TO_NFZ_BENEFIT } from '../../utils/constants'
import { TRIAGE_CLASSES, type TriageClass } from '../../types/medical'
import type { Doctor, DoctorSortBy } from '../../types/doctor'
import { toast } from '../../store/useToastStore'
import { formatWaitDays } from '../../utils/formatters'

type TabId = 'nfz' | 'private' | 'all'

export function DoctorFinderScreen() {
  const selectedSpecialty = useAppStore((s) => s.selectedSpecialty)
  const setSelectedSpecialty = useAppStore((s) => s.setSelectedSpecialty)
  const province = useAppStore((s) => s.selectedProvince)
  const setProvince = useAppStore((s) => s.setSelectedProvince)
  const city = useAppStore((s) => s.selectedCity)
  const setCity = useAppStore((s) => s.setSelectedCity)
  const userLocation = useAppStore((s) => s.userLocation)
  const setUserLocation = useAppStore((s) => s.setUserLocation)

  const [tab, setTab] = useState<TabId>('all')
  const [sortBy, setSortBy] = useState<DoctorSortBy>('wait')

  const geo = useGeolocation()
  const [locationBannerDismissed, setLocationBannerDismissed] = useState(!!userLocation)

  const handleUseMyLocation = () => {
    setLocationBannerDismissed(true)
    geo.request()
  }

  // When GPS resolves, store coords and auto-select province
  useEffect(() => {
    if (geo.status === 'granted' && geo.coords) {
      setUserLocation(geo.coords)
      const guessedProvince = guessProvinceFromCoords(geo.coords.lat, geo.coords.lng)
      setProvince(guessedProvince)
      const provinceLabel = PL_PROVINCES.find((p) => p.code === guessedProvince)?.name
      toast.success(`Located in ${provinceLabel ?? guessedProvince}`, 'Province auto-selected')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geo.status])

  const activeSpecialty: TriageClass = selectedSpecialty ?? 'POZ'
  const activeUserLocation = userLocation ?? (geo.coords ?? null)
  const isER = activeSpecialty === 'ER'

  // ER mode: auto-request location and sort by distance
  useEffect(() => {
    if (isER) {
      setSortBy('distance')
      if (geo.status === 'idle' && !activeUserLocation) {
        setLocationBannerDismissed(false)
      }
    } else {
      setSortBy('wait')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isER])

  const nfzQuery = {
    benefit: TRIAGE_TO_NFZ_BENEFIT[activeSpecialty],
    province,
    case: 1 as const,
  }
  const { run: runNFZ, loading: nfzLoading, data: nfzData, error: nfzError } = useNFZQueues()
  const { run: runDoctors, loading: docLoading, data: docData, error: docError } = useDoctors()

  useEffect(() => {
    void runNFZ(nfzQuery)
    void runDoctors({
      specialty: activeSpecialty,
      city: city || undefined,
      province,
      ...(activeUserLocation
        ? { user_lat: activeUserLocation.lat, user_lng: activeUserLocation.lng }
        : {}),
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSpecialty, province, city, activeUserLocation?.lat, activeUserLocation?.lng])

  useEffect(() => {
    if (nfzError) toast.error(`NFZ: ${nfzError.message}`, 'Could not load NFZ queues')
  }, [nfzError])
  useEffect(() => {
    if (docError) toast.info(`Private listings unavailable: ${docError.message}`)
  }, [docError])

  const nfzEntries = nfzData?.entries ?? []
  const privateDoctors: Doctor[] = useMemo(
    () => (docData?.doctors ?? []).filter((d) => d.source === 'private'),
    [docData],
  )

  const combined: Doctor[] = useMemo(() => {
    const fromNFZ: Doctor[] = nfzEntries.map((e, i) => ({
      id: `nfz-${i}-${e.provider}`,
      source: 'nfz',
      name: e.provider,
      specialty: TRIAGE_LABELS[activeSpecialty].en,
      triageClass: activeSpecialty,
      address: e.address,
      city: e.city,
      province: e.province,
      phone: e.phone,
      waitDays: e.waitDays ?? undefined,
      nextAvailable: e.firstAvailable ?? undefined,
      lat: e.lat,
      lng: e.lng,
    }))
    const all = [...fromNFZ, ...privateDoctors]
    const sorted = [...all].sort((a, b) => {
      if (sortBy === 'wait') return (a.waitDays ?? Infinity) - (b.waitDays ?? Infinity)
      if (sortBy === 'distance') return (a.distanceKm ?? Infinity) - (b.distanceKm ?? Infinity)
      if (sortBy === 'rating') return (b.rating ?? 0) - (a.rating ?? 0)
      return 0
    })
    return sorted
  }, [nfzEntries, privateDoctors, activeSpecialty, sortBy])

  const shown = tab === 'nfz' ? combined.filter((d) => d.source === 'nfz')
    : tab === 'private' ? combined.filter((d) => d.source === 'private')
    : combined

  const bestWait = combined.reduce<number | null>((min, d) => {
    if (d.waitDays == null) return min
    return min == null || d.waitDays < min ? d.waitDays : min
  }, null)

  return (
    <div className="space-y-6">
      <ProgressStepper current={4} />

      <header>
        <h1 className="text-3xl font-extrabold text-slate-900 dark:text-slate-50">
          🏥 Find a doctor
        </h1>
        <p className="mt-2 text-base text-slate-700 dark:text-slate-200">
          {selectedSpecialty ? (
            <>
              Based on your analysis, we're showing <strong>{TRIAGE_LABELS[activeSpecialty].en}</strong>.
            </>
          ) : (
            <>
              Pick a specialty below, or{' '}
              <Link to="/triage" className="font-semibold text-primary-800 hover:underline dark:text-primary-100">
                run an analysis first
              </Link>
              .
            </>
          )}
          {bestWait != null && (
            <>
              {' '}First NFZ appointment in <strong>{formatWaitDays(bestWait)}</strong>.
            </>
          )}
        </p>
      </header>

      {/* ER urgent location banner */}
      {isER && !activeUserLocation && geo.status !== 'loading' && (
        <div className="flex flex-col gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-950/40 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 text-xl leading-none">🚨</span>
            <div>
              <p className="text-sm font-bold text-red-900 dark:text-red-100">
                Emergency — share your location
              </p>
              <p className="mt-0.5 text-xs text-red-700 dark:text-red-300">
                We'll find the nearest SOR/ER hospital within 30 km sorted by distance.
              </p>
            </div>
          </div>
          <div className="flex shrink-0 gap-2 sm:ml-4">
            <Button size="md" onClick={handleUseMyLocation}>
              <Navigation className="h-4 w-4" />
              Use my location
            </Button>
          </div>
        </div>
      )}

      {/* Standard location permission banner (non-ER) */}
      {!isER && !locationBannerDismissed && geo.status === 'idle' && (
        <div className="flex flex-col gap-3 rounded-2xl border border-blue-200 bg-blue-50 p-4 dark:border-blue-800 dark:bg-blue-950/40 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <Navigation className="mt-0.5 h-5 w-5 shrink-0 text-blue-600 dark:text-blue-400" />
            <div>
              <p className="text-sm font-semibold text-blue-900 dark:text-blue-100">
                Find doctors near you
              </p>
              <p className="mt-0.5 text-xs text-blue-700 dark:text-blue-300">
                Share your location to auto-select the right province and see the closest specialists.
              </p>
            </div>
          </div>
          <div className="flex shrink-0 gap-2 sm:ml-4">
            <Button size="md" onClick={handleUseMyLocation}>
              Use my location
            </Button>
            <Button size="md" variant="ghost" onClick={() => setLocationBannerDismissed(true)}>
              Skip
            </Button>
          </div>
        </div>
      )}

      {geo.status === 'loading' && (
        <div className="flex items-center gap-3 rounded-2xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-700 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-300">
          <Navigation className="h-4 w-4 animate-pulse" />
          {isER ? 'Finding nearest emergency departments…' : 'Detecting your location…'}
        </div>
      )}

      <Card padding="none" className="overflow-hidden">
        {/* Filter header */}
        <div className="flex items-center justify-between gap-3 border-b border-slate-100 bg-slate-50 px-5 py-3.5 dark:border-slate-700 dark:bg-slate-800/60">
          <span className="inline-flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
            <Filter className="h-4 w-4 text-primary-600 dark:text-primary-400" aria-hidden="true" />
            Filters
          </span>
          {geo.status === 'granted' && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 ring-1 ring-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-300 dark:ring-emerald-700/40">
              <Navigation className="h-3 w-3" />
              Location active
            </span>
          )}
        </div>

        {/* Filter body */}
        <div className="p-5 sm:p-6">
          <div className={`grid gap-5 ${isER ? 'sm:grid-cols-1 max-w-xs' : 'sm:grid-cols-3'}`}>
            <Select
              label="Specialty"
              value={activeSpecialty}
              onChange={(e) => setSelectedSpecialty(e.target.value as TriageClass)}
              options={TRIAGE_CLASSES.map((c) => ({ value: c, label: TRIAGE_LABELS[c].en }))}
            />
            {!isER && (
              <>
                <Select
                  label="Province"
                  value={province}
                  onChange={(e) => setProvince(e.target.value)}
                  options={PL_PROVINCES.map((p) => ({ value: p.code, label: p.name }))}
                />
                <Input
                  label="City (optional)"
                  placeholder="e.g. Warszawa"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  rightSlot={<MapPin className="h-4 w-4 text-slate-400 pointer-events-none" />}
                />
              </>
            )}
            {isER && activeUserLocation && (
              <p className="text-xs text-slate-500 dark:text-slate-400 self-end pb-3">
                <Navigation className="inline h-3 w-3 mr-1 text-emerald-500" />
                Searching within 30 km of your location
              </p>
            )}
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-slate-100 pt-4 dark:border-slate-700">
            <Tabs<TabId>
              label="Source filter"
              value={tab}
              onChange={setTab}
              tabs={[
                { id: 'all', label: `All (${combined.length})` },
                { id: 'nfz', label: `NFZ (${combined.filter((d) => d.source === 'nfz').length})` },
                { id: 'private', label: `Private (${combined.filter((d) => d.source === 'private').length})` },
              ]}
            />
            <div className="ml-auto flex items-center gap-2">
              <SlidersHorizontal className="h-4 w-4 text-slate-400" aria-hidden="true" />
              <Select
                label=""
                aria-label="Sort by"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as DoctorSortBy)}
                options={[
                  { value: 'wait', label: 'Shortest wait' },
                  { value: 'distance', label: 'Closest' },
                  { value: 'rating', label: 'Best rating' },
                ]}
              />
            </div>
          </div>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-3 lg:col-span-3">
          {(nfzLoading || docLoading) && shown.length === 0 && (
            <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-800">
              <Spinner />
              <span className="text-sm text-slate-700 dark:text-slate-200">
                Searching providers…
              </span>
            </div>
          )}

          {!nfzLoading && !docLoading && shown.length === 0 && (
            <EmptyState
              icon={isER ? <span className="text-3xl">🚨</span> : <MapPin className="h-6 w-6" />}
              title={isER && !activeUserLocation ? 'Share your location' : 'No providers found'}
              description={
                isER && !activeUserLocation
                  ? 'We need your GPS to find the nearest emergency departments within 30 km.'
                  : isER
                  ? 'No emergency departments found within 30 km. Try enabling location or check your connection.'
                  : 'Try another province, a different specialty, or clear the city filter.'
              }
              action={
                isER && !activeUserLocation ? (
                  <Button onClick={handleUseMyLocation}>
                    <Navigation className="h-4 w-4" />
                    Use my location
                  </Button>
                ) : !isER ? (
                  <Button variant="secondary" onClick={() => setCity('')}>
                    Clear city filter
                  </Button>
                ) : undefined
              }
            />
          )}

          {shown.map((d) => (
            <DoctorCard key={d.id} doctor={d} />
          ))}

          {tab !== 'all' && tab === 'nfz' && nfzEntries.length > 0 && (
            <div className="mt-2">
              <h3 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
                Raw NFZ queue entries
              </h3>
              <NFZQueues entries={nfzEntries} />
            </div>
          )}
        </div>

        <div className="lg:col-span-2">
          <Card padding="md" title="Map">
            <DoctorMap doctors={shown} userLocation={activeUserLocation ?? undefined} />
          </Card>
        </div>
      </div>

      <Disclaimer />
    </div>
  )
}
