import { useQuery } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { StatusPill } from '../components/StatusPill'
import { api } from '../lib/api'

export function McpPage() {
  const status = useQuery({ queryKey: ['mcp-status'], queryFn: api.mcpStatus, retry: false })
  return <div className="page-stack">
    <header className="page-header"><div><p className="eyebrow">Local stdio subprocess</p><h1>MCP tools</h1></div><button className="secondary-button" onClick={() => status.refetch()}><RefreshCw size={16} />Reconnect</button></header>
    <section className="panel">
      <div className="panel-heading"><div><h2>{status.data?.server_name ?? 'AWS MCP server'}</h2><p>{status.data?.message ?? 'Connecting to the local MCP subprocess…'}</p></div><StatusPill tone={status.data?.connected ? 'good' : 'bad'}>{status.data?.connected ? 'Connected' : 'Unavailable'}</StatusPill></div>
      {status.data?.protocol_version && <p className="muted">Protocol {status.data.protocol_version}</p>}
    </section>
    <section className="tool-grid">{status.data?.tools.map((tool) => <article className="panel tool-card" key={tool.name}><h2>{tool.name}</h2><p>{tool.description}</p><small>{Object.keys((tool.input_schema.properties as object | undefined) ?? {}).length} input fields</small></article>)}</section>
  </div>
}
