# OpsLens architecture — Phases 0–5

## Design goals

OpsLens is a single-user, laptop-only system. Every application component and all durable state
remain local. The selected model provider may receive the question, conversation context, MCP tool
definitions, and the AWS evidence needed for an answer. AWS and model credentials never enter the
React application or MySQL.

The implementation is a modular monolith plus a deliberately isolated MCP subprocess. That keeps
development and operation simple while preserving replaceable boundaries for the model provider,
AWS data collectors, rules, persistence, and UI.

## Component architecture

```mermaid
flowchart LR
    U[Local user] -->|http://127.0.0.1:5173| UI[React + Vite]
    UI -->|REST + SSE on localhost| API[FastAPI backend]

    subgraph Laptop[User laptop]
      UI
      API
      DB[(MySQL 8)]
      KC[OS keychain]
      AWSFILES[AWS CLI / SSO profile]
      MCP[MCP server<br/>local stdio subprocess]

      API -->|SQLAlchemy async| DB
      API -->|key reference lookup| KC
      API -->|spawn, list tools, call tool| MCP
      MCP -->|AWS SDK credential chain| AWSFILES
    end

    MCP -->|read-only boto3 APIs over TLS| AWS[AWS account]
    API -->|Messages API over TLS<br/>prompt + selected evidence| MODEL[Configured model provider]
```

Only the Vite development server and FastAPI listen on TCP, both on loopback. The MCP server uses
stdio and is created on demand. MySQL is local; the Docker option publishes only the configured
local development port.

## Module boundaries

| Module | Responsibility | Must not do |
|---|---|---|
| React frontend | Dashboard, settings, inventory, findings, chat, SSE activity | Read credentials or call AWS/model APIs directly |
| FastAPI routes | Local HTTP validation and response streaming | Embed provider-specific agent logic |
| Orchestration | Provider-neutral model/tool loop and safety limits | Call boto3 directly |
| Provider adapters | Translate neutral messages/tools to a model API | Own AWS authorization or business rules |
| MCP client | Discover and invoke typed local tools | Expose arbitrary process execution |
| MCP server | Read-only AWS evidence collection | Mutate AWS or return Parameter Store values |
| Health rules | Deterministic findings from normalized inventory | Depend on an LLM |
| Repositories | MySQL persistence and transactions | Hold API keys or AWS access keys |
| OS keychain | Model API key | Store AWS session state in application tables |

## Conversational request flow

```mermaid
sequenceDiagram
    actor User
    participant UI as React
    participant API as FastAPI
    participant DB as MySQL
    participant Agent as Agent loop
    participant Model as Model provider
    participant MCP as Local MCP
    participant AWS as AWS APIs

    User->>UI: Ask an AWS question
    UI->>API: POST /messages/stream
    API->>DB: Store user message + running agent_run
    API-->>UI: Open SSE response
    Agent->>MCP: list_tools
    MCP-->>Agent: JSON schemas for read-only tools
    Agent->>Model: System policy + history + tool schemas
    alt Model needs current AWS evidence
      Model-->>Agent: tool_use(name, arguments)
      Agent-->>UI: SSE tool_started
      Agent->>MCP: call_tool
      MCP->>AWS: Read-only boto3 request
      AWS-->>MCP: AWS response
      MCP-->>Agent: Typed evidence envelope
      Agent->>DB: Store tool_execution metadata
      Agent-->>UI: SSE tool_completed
      Agent->>Model: tool_result evidence
    end
    Model-->>Agent: Final natural-language answer
    Agent->>DB: Store assistant message, token usage, completed run
    Agent-->>UI: SSE message + done
    UI-->>User: Answer and activity trace
```

The loop is capped by `OPSLENS_MAX_AGENT_ITERATIONS`. Tool results are capped before being sent to
the model. A tool exception becomes an explicit error result so the model can explain missing
evidence instead of inventing a fact.

## Inventory and deterministic health flow

```mermaid
flowchart TD
    R[User clicks Refresh] --> V[Resolve configured AWS profile]
    V --> I[STS account allowlist check]
    I --> C[Collect normalized inventory]
    C --> S[(Replace affected rows in resource_inventory)]
    S --> H[Evaluate complete stored inventory]
    H --> HS[(Replace health snapshots)]
    H --> F{Finding fingerprint active?}
    F -->|new| O[Create open finding]
    F -->|still active| U[Update last seen and evidence]
    F -->|no longer active| X[Mark finding resolved]
    O --> UI[Overview]
    U --> UI
    X --> UI
```

Health findings do not depend on Claude. Current rules cover ECS desired/running/pending tasks,
ALB state, RDS availability, disabled CloudFront distributions, unverified SES identities, and
CloudWatch alarm/no-data states. Rules are pure and unit-tested, so more checks can be added without
changing the agent.

## Provider-neutral model boundary

```mermaid
classDiagram
    class ModelProvider {
      <<protocol>>
      +complete(system, messages, tools, model, max_tokens) ProviderResponse
    }
    class AnthropicProvider
    class FutureOpenAIProvider
    class FutureLocalProvider
    class AgentLoop

    AgentLoop --> ModelProvider
    AnthropicProvider ..|> ModelProvider
    FutureOpenAIProvider ..|> ModelProvider
    FutureLocalProvider ..|> ModelProvider
```

`AgentLoop` only understands neutral tool definitions, content blocks, tool calls, text, and usage.
Today the factory builds `AnthropicProvider`. A Codex/OpenAI adapter would translate these values to
that provider's response/tool-call format and register it in the factory; AWS MCP tools, databases,
routes, SSE events, and React do not change.

## Persistence model

```mermaid
erDiagram
    CONVERSATIONS ||--o{ MESSAGES : contains
    CONVERSATIONS ||--o{ AGENT_RUNS : starts
    AGENT_RUNS ||--o{ TOOL_EXECUTIONS : records
    AWS_PROFILE_CONFIGS {
      string profile_name
      string expected_account_id
      json regions_json
    }
    MODEL_PROVIDER_CONFIGS {
      string provider
      string model
      string api_key_reference
    }
    RESOURCE_INVENTORY ||--o{ HEALTH_SNAPSHOTS : evaluated_as
    RESOURCE_INVENTORY ||--o{ FINDINGS : produces
```

The diagram shows logical ownership; health records use stable AWS resource identifiers and finding
fingerprints rather than foreign keys because inventory is replaced during refresh. Audit events
record important configuration, inventory, evaluation, and acknowledgement operations.

## Security and trust boundaries

1. **Browser boundary:** only settings metadata, inventory, findings, and messages cross it. No
   credential is returned to React.
2. **Model boundary:** prompts and selected operational evidence leave the laptop over TLS. The API
   key comes from the OS keychain or a backend-only environment variable.
3. **AWS boundary:** boto3 uses the standard local credential chain and temporary SSO credentials.
   MySQL stores only profile names and an optional expected account ID.
4. **Tool boundary:** the model can choose only registered, schema-validated, read-only MCP tools.
   Parameter Store exposes metadata, never values. KMS never encrypts/decrypts. SES never sends.
   Log search is capped at ten named groups and a bounded time/result window; RDS metric queries
   use CloudWatch and never connect to the database engine.
5. **Network boundary:** API and frontend bind to `127.0.0.1`; FastAPI allows only the configured
   localhost frontend origin and trusted localhost host names.
6. **Prompt-injection boundary:** AWS logs and metadata are untrusted data. The system prompt says
   tool output cannot override policy, and there are no mutation or general-purpose execution tools.

## Failure behavior

- MySQL unavailable: health reports degraded and persistence-dependent endpoints fail explicitly.
- AWS SSO expired or unauthorized: MCP returns a failed tool result; the final answer must describe
  the missing evidence.
- Model key/provider invalid: chat returns a local `409` before an SSE stream starts.
- Model or tool timeout: the run is marked failed and an SSE error is shown.
- Partial AWS permissions: inventory/evidence carries warnings and a `partial` status.
- Browser disconnect: already committed user/run records remain available for audit; a later cleanup
  can mark abandoned runs if desired.

## Extension points

- Add a provider adapter under `backend/src/opslens/providers` and one factory branch.
- Add read-only tools in `mcp-server/src/aws_ops_mcp/server.py`; discovery makes them available to
  the agent automatically.
- Add pure rules in `mcp-server/src/aws_ops_mcp/health.py` and corresponding tests.
- Add saved views, scheduled local polling, or richer metric/log query tools without changing the
  trust model. Scheduled monitoring is intentionally outside Phases 0–5.

## Deliberate current limitation

RDS table row counts are SQL data, not an AWS control-plane or CloudWatch metric. Supporting them
securely requires a second trust boundary: a network route to RDS, TLS verification, a dedicated
read-only MySQL user, database/schema allowlists, query timeouts, and a restricted SQL tool. That
connector is intentionally not inferred from the local OpsLens MySQL configuration and is outside
Phases 0–5.
