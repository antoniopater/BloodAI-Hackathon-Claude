import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Filter, MapPin } from 'lucide-react'
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
import { useAppStore } from '../../store/useAppStore'
import { useDoctors, useNFZQueues } from '../../hooks/useNFZQueues'
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

  const [tab, setTab] = useState<TabId>('all')
  const [sortBy, setSortBy] = useState<DoctorSortBy>('wait')

  const activeSpecialty: TriageClass = selectedSpecialty ?? 'POZ'

  const nfzQuery = {
    benefit: TRIAGE_TO_NFZ_BENEFIT[activeSpecialty],
    province,
    case: 1 as const,
  }
  const { run: runNFZ, loading: nfzLoading, data: nfzData, error: nfzError } = useNFZQueues()
  const { run: runDoctors, loading: docLoading, data: docData, error: docError } = useDoctors()

  useEffect(() => {
    void runNFZ(nfzQuery)
    void runDoctors({ specialty: activeSpecialty, city: city || undefined, province })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSpecialty, province, city])

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

      <Card padding="md" title={<span className="inline-flex items-center gap-2"><Filter className="h-5 w-5" aria-hidden="true" />Filters</span>}>
        <div className="grid gap-4 sm:grid-cols-3">
          <Select
            label="Specialty"
            value={activeSpecialty}
            onChange={(e) => setSelectedSpecialty(e.target.value as TriageClass)}
            options={TRIAGE_CLASSES.map((c) => ({ value: c, label: TRIAGE_LABELS[c].en }))}
          />
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
          />
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3">
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
          <div className="ml-auto">
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
              icon={<MapPin className="h-6 w-6" />}
              title="No providers found"
              description="Try another province, a different specialty, or clear the city filter."
              action={
                <Button variant="secondary" onClick={() => setCity('')}>
                  Clear city filter
                </Button>
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
            <DoctorMap doctors={shown} />
          </Card>
        </div>
      </div>

      <Disclaimer />
    </div>
  )
}
