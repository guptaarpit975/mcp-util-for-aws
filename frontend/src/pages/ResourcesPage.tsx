import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { StatusPill } from '../components/StatusPill'
import { api } from '../lib/api'

export function ResourcesPage() {
  const queryClient = useQueryClient()
  const [service, setService] = useState('')
  const [region, setRegion] = useState('')
  const [search, setSearch] = useState('')
  const params = new URLSearchParams()
  if (service) params.set('service', service)
  if (region) params.set('region', region)
  if (search) params.set('search', search)
  const suffix = params.size ? `?${params.toString()}` : ''
  const resources = useQuery({ queryKey: ['resources', suffix], queryFn: () => api.resources(suffix) })
  const refresh = useMutation({
    mutationFn: api.refreshResources,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['resources'] }),
  })
  const allItems = useMemo(() => resources.data?.items ?? [], [resources.data?.items])
  const services = useMemo(() => [...new Set(allItems.map((item) => item.service))].sort(), [allItems])
  const regions = useMemo(() => [...new Set(allItems.map((item) => item.region))].sort(), [allItems])

  return (
    <div className="page-stack">
      <header className="page-header"><div><p className="eyebrow">Read-only AWS inventory</p><h1>Resources</h1></div><button className="primary-button" onClick={() => refresh.mutate()} disabled={refresh.isPending}><RefreshCw size={16} />{refresh.isPending ? 'Refreshing…' : 'Refresh inventory'}</button></header>
      {refresh.isError && <div className="notice error">{refresh.error.message}</div>}
      {refresh.data && <div className="notice success">Collected {refresh.data.resource_count} resources with {refresh.data.warning_count} warnings.</div>}
      <section className="filter-row">
        <select value={service} onChange={(event) => setService(event.target.value)} aria-label="Service filter"><option value="">All services</option>{services.map((item) => <option key={item}>{item}</option>)}</select>
        <select value={region} onChange={(event) => setRegion(event.target.value)} aria-label="Region filter"><option value="">All regions</option>{regions.map((item) => <option key={item}>{item}</option>)}</select>
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search resource name" aria-label="Search resources" />
      </section>
      <section className="panel table-panel">
        <table><thead><tr><th>Resource</th><th>Service</th><th>Region</th><th>Status</th><th>Collected</th></tr></thead><tbody>
          {allItems.map((item) => <tr key={item.id}><td><strong>{item.name}</strong><small>{item.resource_type}</small></td><td>{item.service}</td><td>{item.region}</td><td><StatusPill tone={item.status === 'degraded' || item.status === 'alarm' ? 'bad' : item.status === 'unknown' ? 'neutral' : 'good'}>{item.status}</StatusPill></td><td>{new Date(item.collected_at).toLocaleString()}</td></tr>)}
          {!resources.isLoading && allItems.length === 0 && <tr><td colSpan={5} className="empty-state">No resources found. Configure AWS and refresh inventory.</td></tr>}
        </tbody></table>
      </section>
    </div>
  )
}
