import type {
  AwsConnection,
  AwsProfile,
  ChatEvent,
  ChatMessage,
  Conversation,
  FindingList,
  Health,
  HealthSummary,
  InventoryRefresh,
  McpStatus,
  ModelProvider,
  ResourceList,
  Settings,
  Validation,
} from './types'

const API = '/api/v1'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(body.detail ?? `Request failed with ${response.status}`)
  }
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<Health>('/health'),
  settings: () => request<Settings>('/settings'),
  updateModel: (value: Omit<ModelProvider, 'api_key_configured' | 'api_key_reference'>) =>
    request<ModelProvider>('/settings/model', { method: 'PUT', body: JSON.stringify(value) }),
  storeModelSecret: (api_key: string) =>
    request<Validation>('/settings/model/secret', {
      method: 'POST',
      body: JSON.stringify({ api_key }),
    }),
  testModel: () => request<Validation>('/settings/model/test', { method: 'POST' }),
  updateAws: (value: AwsProfile) =>
    request<AwsProfile>('/settings/aws', { method: 'PUT', body: JSON.stringify(value) }),
  testMysql: () => request<Validation>('/settings/mysql/test', { method: 'POST' }),
  awsStatus: () => request<AwsConnection>('/aws/status'),
  resources: (params = '') => request<ResourceList>(`/resources${params}`),
  refreshResources: () =>
    request<InventoryRefresh>('/resources/refresh', {
      method: 'POST',
      body: JSON.stringify({ services: null }),
    }),
  mcpStatus: () => request<McpStatus>('/mcp/status'),
  healthSummary: () => request<HealthSummary>('/health/summary'),
  findings: (status = 'open') => request<FindingList>(`/findings?status=${status}`),
  conversations: () => request<Conversation[]>('/conversations'),
  createConversation: (title = 'New conversation') =>
    request<Conversation>('/conversations', {
      method: 'POST',
      body: JSON.stringify({ title }),
    }),
  messages: (conversationId: string) =>
    request<ChatMessage[]>(`/conversations/${conversationId}/messages`),
  streamMessage: async (
    conversationId: string,
    content: string,
    onEvent: (event: ChatEvent) => void,
  ) => {
    const response = await fetch(`${API}/conversations/${conversationId}/messages/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    })
    if (!response.ok) {
      const body = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(body.detail ?? `Request failed with ${response.status}`)
    }
    if (!response.body) throw new Error('The browser did not expose the response stream.')
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })
      const frames = buffer.split('\n\n')
      buffer = frames.pop() ?? ''
      for (const frame of frames) {
        const data = frame.split('\n').find((line) => line.startsWith('data: '))
        if (data) onEvent(JSON.parse(data.slice(6)) as ChatEvent)
      }
      if (done) break
    }
  },
}
