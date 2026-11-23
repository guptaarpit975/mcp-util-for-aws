export type Health = {
  status: 'ok' | 'degraded'
  application: string
  environment: string
  database: string
}

export type AwsConnection = {
  connected: boolean
  profile: string
  account_id?: string
  arn?: string
  user_id?: string
  message: string
}

export type ModelProvider = {
  provider: 'anthropic' | 'openai' | 'local'
  model: string
  base_url?: string
  api_key_reference?: string
  api_key_configured: boolean
  enabled: boolean
  options: Record<string, unknown>
}

export type AwsProfile = {
  profile_name: string
  expected_account_id?: string
  regions: string[]
  enabled: boolean
}

export type Settings = {
  model_provider: ModelProvider
  aws_profile: AwsProfile | null
}

export type Resource = {
  id: string
  account_id: string
  region: string
  service: string
  resource_type: string
  resource_id: string
  name: string
  arn?: string
  status: string
  metadata_json: Record<string, unknown>
  collected_at: string
}

export type ResourceList = { items: Resource[]; total: number }

export type InventoryRefresh = {
  account_id: string
  resource_count: number
  warning_count: number
  warnings: string[]
  collected_at: string
}

export type McpTool = {
  name: string
  title?: string
  description?: string
  input_schema: Record<string, unknown>
}

export type McpStatus = {
  connected: boolean
  server_name?: string
  protocol_version?: string
  tools: McpTool[]
  message: string
}

export type Validation = { ok: boolean; message: string }

export type HealthSummary = {
  total_resources: number
  healthy_resources: number
  open_findings: number
  critical_findings: number
  warning_findings: number
  last_evaluated_at?: string
}

export type Finding = {
  id: string
  account_id: string
  region: string
  service: string
  resource_type: string
  resource_id: string
  resource_name: string
  code: string
  severity: 'critical' | 'warning' | 'info'
  status: 'open' | 'acknowledged' | 'resolved'
  summary: string
  first_seen_at: string
  last_seen_at: string
}

export type FindingList = { items: Finding[]; total: number }

export type Conversation = {
  id: string
  title: string
  provider?: string
  model?: string
  created_at: string
  updated_at: string
}

export type ChatMessage = {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export type ChatEvent = {
  type: 'status' | 'tool_started' | 'tool_completed' | 'message' | 'done' | 'error'
  message?: string
  content?: string
  tool?: string
  status?: string
  duration_ms?: number
  arguments?: Record<string, unknown>
}
