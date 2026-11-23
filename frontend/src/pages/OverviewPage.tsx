import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { AlertTriangle, Cloud, Database, PlugZap } from 'lucide-react'
import { StatusPill } from '../components/StatusPill'
import { api } from '../lib/api'

export function OverviewPage() {
  const health = useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 30_000 })
  const aws = useQuery({ queryKey: ['aws-status'], queryFn: api.awsStatus, retry: false })
  const resources = useQuery({ queryKey: ['resources'], queryFn: () => api.resources() })
  const mcp = useQuery({ queryKey: ['mcp-status'], queryFn: api.mcpStatus, retry: false })
  const healthSummary = useQuery({ queryKey: ['health-summary'], queryFn: api.healthSummary })
  const findings = useQuery({ queryKey: ['findings'], queryFn: () => api.findings('open') })

  const counts = new Map<string, number>()
  resources.data?.items.forEach((item) => counts.set(item.service, (counts.get(item.service) ?? 0) + 1))

  return (
    <div className="page-stack">
      <header className="page-header">
        <div><p className="eyebrow">Local application</p><h1>Environment overview</h1></div>
      </header>

      <section className="stat-grid">
        <article className="stat"><Database /><span>Local MySQL</span><strong>{health.data?.database ?? 'Checking'}</strong></article>
        <article className="stat"><Cloud /><span>AWS profile</span><strong>{aws.data?.connected ? 'Connected' : 'Not connected'}</strong></article>
        <article className="stat"><AlertTriangle /><span>Open findings</span><strong>{healthSummary.data?.open_findings ?? 0}</strong></article>
        <article className="stat"><PlugZap /><span>MCP server</span><strong>{mcp.data?.connected ? `${mcp.data.tools.length} tools` : 'Unavailable'}</strong></article>
      </section>

      <section className="two-column">
        <article className="panel">
          <div className="panel-heading"><div><h2>Runtime status</h2><p>Local services and configured AWS access.</p></div></div>
          <div className="status-list">
            <div><span>FastAPI</span><StatusPill tone={health.data?.status === 'ok' ? 'good' : 'warning'}>{health.data?.status ?? 'Checking'}</StatusPill></div>
            <div><span>MySQL</span><StatusPill tone={health.data?.database === 'connected' ? 'good' : 'bad'}>{health.data?.database ?? 'Checking'}</StatusPill></div>
            <div><span>AWS</span><StatusPill tone={aws.data?.connected ? 'good' : 'warning'}>{aws.data?.connected ? aws.data.account_id : 'Configure'}</StatusPill></div>
            <div><span>Local MCP</span><StatusPill tone={mcp.data?.connected ? 'good' : 'bad'}>{mcp.data?.connected ? 'Connected' : 'Unavailable'}</StatusPill></div>
          </div>
        </article>

        <article className="panel">
          <div className="panel-heading"><div><h2>Inventory by service</h2><p>Refresh inventory from the Resources screen.</p></div><Link className="text-link" to="/resources">Open resources</Link></div>
          {counts.size === 0 ? <p className="empty-state">No inventory has been collected yet.</p> : (
            <div className="service-counts">{[...counts.entries()].map(([service, count]) => <div key={service}><span>{service}</span><strong>{count}</strong></div>)}</div>
          )}
        </article>
      </section>
      <section className="panel">
        <div className="panel-heading"><div><h2>Findings requiring attention</h2><p>Deterministic checks from the latest stored inventory.</p></div><Link className="text-link" to="/assistant">Ask AI</Link></div>
        {!findings.data?.items.length ? <p className="empty-state">No open findings. Refresh inventory to run the checks.</p> : <div className="finding-list">{findings.data.items.slice(0, 8).map((item) => <div key={item.id}><StatusPill tone={item.severity === 'critical' ? 'bad' : 'warning'}>{item.severity}</StatusPill><span><strong>{item.resource_name}</strong><small>{item.service} · {item.region}</small></span><p>{item.summary}</p></div>)}</div>}
      </section>
    </div>
  )
}
