import { FormEvent, useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'

export function SettingsPage() {
  const queryClient = useQueryClient()
  const settings = useQuery({ queryKey: ['settings'], queryFn: api.settings })
  const [provider, setProvider] = useState<'anthropic' | 'openai' | 'local'>('anthropic')
  const [model, setModel] = useState('claude-sonnet-5-5')
  const [baseUrl, setBaseUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [profile, setProfile] = useState('')
  const [account, setAccount] = useState('')
  const [regions, setRegions] = useState('ap-south-1, us-east-1')
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!settings.data) return
    setProvider(settings.data.model_provider.provider)
    setModel(settings.data.model_provider.model)
    setBaseUrl(settings.data.model_provider.base_url ?? '')
    setProfile(settings.data.aws_profile?.profile_name ?? '')
    setAccount(settings.data.aws_profile?.expected_account_id ?? '')
    setRegions(settings.data.aws_profile?.regions.join(', ') ?? '')
  }, [settings.data])

  const saveModel = useMutation({ mutationFn: api.updateModel, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['settings'] }) })
  const saveSecret = useMutation({ mutationFn: api.storeModelSecret, onSuccess: (value) => { setMessage(value.message); setApiKey(''); queryClient.invalidateQueries({ queryKey: ['settings'] }) } })
  const saveAws = useMutation({ mutationFn: api.updateAws, onSuccess: () => { setMessage('AWS profile saved.'); queryClient.invalidateQueries({ queryKey: ['settings'] }); queryClient.invalidateQueries({ queryKey: ['aws-status'] }) } })

  function submitModel(event: FormEvent) {
    event.preventDefault()
    saveModel.mutate({ provider, model, base_url: baseUrl || undefined, enabled: true, options: {} })
  }
  function submitAws(event: FormEvent) {
    event.preventDefault()
    saveAws.mutate({ profile_name: profile, expected_account_id: account || undefined, regions: regions.split(',').map((item) => item.trim()).filter(Boolean), enabled: true })
  }

  return <div className="page-stack">
    <header className="page-header"><div><p className="eyebrow">Stored locally</p><h1>Settings</h1></div></header>
    {message && <div className="notice success">{message}</div>}
    <div className="settings-grid">
      <form className="panel form-panel" onSubmit={submitModel}><div className="panel-heading"><div><h2>Model provider</h2><p>The conversation loop currently ships with the Anthropic adapter; its boundary is provider-neutral.</p></div></div><label>Provider<select value={provider} onChange={(event) => setProvider(event.target.value as typeof provider)}><option value="anthropic">Anthropic</option><option value="openai">OpenAI (adapter not installed)</option><option value="local">Local (adapter not installed)</option></select></label><label>Model<input value={model} onChange={(event) => setModel(event.target.value)} required /></label><label>Base URL<input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="Provider default" /></label><button className="primary-button" type="submit">Save provider</button><hr /><label>API key<input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder={settings.data?.model_provider.api_key_configured ? 'Stored in keychain' : 'Not configured'} /></label><button className="secondary-button" type="button" disabled={apiKey.length < 8} onClick={() => saveSecret.mutate(apiKey)}>Store in keychain</button></form>
      <form className="panel form-panel" onSubmit={submitAws}><div className="panel-heading"><div><h2>AWS connection</h2><p>Use a read-only IAM Identity Center profile.</p></div></div><label>Profile name<input value={profile} onChange={(event) => setProfile(event.target.value)} placeholder="personal-ops" required /></label><label>Expected account ID<input value={account} onChange={(event) => setAccount(event.target.value)} placeholder="Optional 12-digit allowlist" pattern="[0-9]{12}" /></label><label>Regions<input value={regions} onChange={(event) => setRegions(event.target.value)} required /></label><button className="primary-button" type="submit">Save AWS profile</button><button className="secondary-button" type="button" onClick={async () => { const result = await api.awsStatus(); setMessage(result.message) }}>Test AWS access</button></form>
      <section className="panel form-panel"><div className="panel-heading"><div><h2>Local MySQL</h2><p>The connection URL comes from the local environment.</p></div></div><button className="secondary-button" type="button" onClick={async () => { const result = await api.testMysql(); setMessage(result.message) }}>Test MySQL</button></section>
    </div>
  </div>
}
