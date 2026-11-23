# OpsLens local runbook

All commands in this document are run from:

```bash
cd /Users/arpit.gupta.85/Business-Repo-YourHealthMatters/mcp-util-for-aws
```

## 1. Prerequisites

- Python 3.12 or newer and [`uv`](https://docs.astral.sh/uv/)
- Node.js 20 or newer and `pnpm`
- Docker Desktop, unless an existing MySQL 8 instance will be used
- AWS CLI v2 with an IAM Identity Center (SSO) profile
- An Anthropic API key. A Claude Pro web subscription does **not** include Claude API usage; the
  key must come from an Anthropic Console API account with billing enabled. See Anthropic's
  [official Pro plan explanation](https://support.claude.com/en/articles/8325606-what-is-the-pro-plan).

Install application dependencies once:

```bash
uv sync --all-packages --all-extras
pnpm install
```

## 2. Environment variables to put in the terminal

The application also reads a `.env` file in the repository root. Start with:

```bash
cp .env.example .env
```

For a terminal-only setup, export these before starting the backend or running migrations:

```bash
export OPSLENS_ENVIRONMENT='development'
export OPSLENS_HOST='127.0.0.1'
export OPSLENS_PORT='8000'
export OPSLENS_FRONTEND_ORIGIN='http://127.0.0.1:5173'
export OPSLENS_DATABASE_URL='mysql+asyncmy://opslens:opslens@127.0.0.1:3307/opslens'
export OPSLENS_AUTO_CREATE_SCHEMA='false'
export OPSLENS_DEFAULT_AWS_PROFILE='personal-ops'
export OPSLENS_DEFAULT_AWS_REGIONS='ap-south-1,us-east-1'
export OPSLENS_MCP_TOOL_TIMEOUT_SECONDS='30'
export OPSLENS_INVENTORY_PAGE_LIMIT='10'
export OPSLENS_MAX_AGENT_ITERATIONS='6'
export OPSLENS_MAX_TOOL_RESULT_CHARS='50000'
export OPSLENS_MODEL_MAX_TOKENS='2048'
```

Change `personal-ops` and the region list to match the local AWS CLI profile. The variables are:

| Variable | Required | Purpose |
|---|---:|---|
| `OPSLENS_DATABASE_URL` | yes | Async SQLAlchemy URL for the local MySQL database |
| `OPSLENS_DEFAULT_AWS_PROFILE` | yes, unless saved in UI | Local AWS CLI profile name; never an access key |
| `OPSLENS_DEFAULT_AWS_REGIONS` | yes | Comma-separated regional collection scope |
| `OPSLENS_HOST` | no | API bind address; keep `127.0.0.1` |
| `OPSLENS_PORT` | no | API port, default `8000` |
| `OPSLENS_FRONTEND_ORIGIN` | no | Only browser origin allowed by CORS |
| `OPSLENS_AUTO_CREATE_SCHEMA` | no | Keep `false`; use versioned Alembic migrations |
| `OPSLENS_MCP_TOOL_TIMEOUT_SECONDS` | no | Per-call MCP timeout |
| `OPSLENS_INVENTORY_PAGE_LIMIT` | no | Safety cap for paginated AWS enumeration |
| `OPSLENS_MAX_AGENT_ITERATIONS` | no | Stops runaway model/tool loops |
| `OPSLENS_MAX_TOOL_RESULT_CHARS` | no | Caps evidence sent back to the model per tool |
| `OPSLENS_MODEL_MAX_TOKENS` | no | Maximum model output per agent iteration |
| `OPSLENS_MYSQL_PORT` | no | Host port for Docker MySQL, default `3307` |
| `AWS_CONFIG_FILE` | no | Non-default path to the AWS CLI config, forwarded to MCP |
| `AWS_SHARED_CREDENTIALS_FILE` | no | Non-default credentials-file path, forwarded to MCP |
| `OPSLENS_AWS_PROFILE` | manual MCP only | Profile used only when starting the MCP process yourself |

### Model API key

Preferred: start the app, open **Settings**, save the Anthropic provider/model, and store the API
key. It is placed in the operating-system keychain; MySQL stores only a reference.

Environment fallback for a single terminal session:

```bash
read -s 'ANTHROPIC_API_KEY?Anthropic API key: '
export ANTHROPIC_API_KEY
echo
```

Do not add a real API key to `.env`, shell history, Git, frontend environment variables, or MySQL.
The backend also recognizes `OPENAI_API_KEY` for a future OpenAI/Codex adapter, but that adapter is
not part of this phase.

## 3. Database setup and scripts

### Option A: isolated Docker MySQL (recommended)

Start it and confirm its health:

```bash
docker compose up -d mysql
docker compose ps
```

The Docker database listens on `127.0.0.1:3307` with database/user/password `opslens`. This is a
local-development credential, not an internet-facing configuration.

Apply every pending schema migration:

```bash
uv run --package opslens-api alembic -c backend/alembic.ini upgrade head
```

Inspect the applied revision and verify that models and migrations agree:

```bash
uv run --package opslens-api alembic -c backend/alembic.ini current
uv run --package opslens-api alembic -c backend/alembic.ini check
```

Stop MySQL without deleting its data:

```bash
docker compose stop mysql
```

### Option B: an existing local MySQL 8 server

Run the following as a local MySQL administrator, replacing the password:

```sql
CREATE DATABASE opslens CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'opslens'@'127.0.0.1' IDENTIFIED BY 'choose-a-local-password';
GRANT ALL PRIVILEGES ON opslens.* TO 'opslens'@'127.0.0.1';
FLUSH PRIVILEGES;
```

Then export an encoded connection URL and run `alembic upgrade head`:

```bash
export OPSLENS_DATABASE_URL='mysql+asyncmy://opslens:choose-a-local-password@127.0.0.1:3306/opslens'
uv run --package opslens-api alembic -c backend/alembic.ini upgrade head
```

Alembic migration files are under `backend/alembic/versions`. Do not enable automatic schema
creation for normal use.

## 4. AWS login and least privilege

Create and log in to an IAM Identity Center profile:

```bash
aws configure sso --profile personal-ops
aws sso login --profile personal-ops
aws sts get-caller-identity --profile personal-ops
```

Use a read-only permission set. Save the 12-digit expected account ID in Settings; this makes the
backend reject a profile that resolves to a different account. SSO expiry is normal—repeat the
`aws sso login` command when AWS reports expired credentials.

In addition to the list/describe permissions for the supported services, conversational log and
metric questions need `logs:DescribeLogGroups`, `logs:FilterLogEvents`, and
`cloudwatch:GetMetricData`. Keep the resource scope as narrow as practical for the account.

## 5. Start each service

Use separate terminals so logs remain easy to read.

### Terminal 1 — MySQL

```bash
docker compose up -d mysql
docker compose ps
```

### Terminal 2 — FastAPI backend (and MCP client)

Export the variables from section 2, then:

```bash
uv run --package opslens-api uvicorn opslens.main:app \
  --reload --host 127.0.0.1 --port 8000
```

API documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### Terminal 3 — React frontend

```bash
pnpm --dir frontend dev
```

Application: [http://127.0.0.1:5173](http://127.0.0.1:5173).

### MCP server

The MCP server does **not** need its own long-running terminal. The backend starts a fresh local
stdio subprocess when it inspects or invokes a tool. To run it manually for debugging:

```bash
export OPSLENS_AWS_PROFILE='personal-ops'
export OPSLENS_INVENTORY_PAGE_LIMIT='10'
uv run --package aws-ops-mcp aws-ops-mcp
```

It will appear idle because stdio MCP waits for a client. Stop it with `Ctrl-C`. Do not run a
second MCP server for normal application use.

### Convenience commands

```bash
make mysql      # Docker MySQL
make migrate    # Alembic upgrade to head
make backend    # FastAPI only
make frontend   # Vite only
make mcp        # manual stdio MCP debugging only
make dev        # backend + frontend; MySQL must already be running
```

## 6. First-use workflow

1. Open **Settings** and save `anthropic` plus a currently available Claude model ID.
2. Store the API key in the OS keychain, or export `ANTHROPIC_API_KEY` before backend startup.
3. Save the AWS profile, expected account ID, and desired regions; test AWS access.
4. Open **Resources** and refresh inventory.
5. Review deterministic findings on **Overview**.
6. Open **Ask AI** and ask a question. Tool activity appears while the agent gathers evidence.

Supported examples include ECS desired/running health, service inventory, CloudWatch alarms,
reference-ID searches across up to ten selected log groups, and RDS CPU/connections/memory/storage/
IOPS metrics. “Rows in every MySQL table” is not available in this release: that information is not
an AWS control-plane metric and would require a separate read-only MySQL network connection and SQL
credential. OpsLens does not silently reuse the application's own local MySQL credential for RDS.

The provider field accepts `openai` and `local` to preserve configuration portability, but this
release intentionally returns a clear configuration error until those adapters are installed.

## 7. Validation and troubleshooting

Run the complete local verification suite:

```bash
uv run ruff check backend mcp-server
uv run ruff format --check backend mcp-server
uv run pytest -q
pnpm --dir frontend lint
pnpm --dir frontend build
uv run --package opslens-api alembic -c backend/alembic.ini check
```

Quick runtime checks:

```bash
curl -s http://127.0.0.1:8000/api/v1/health
curl -s http://127.0.0.1:8000/api/v1/mcp/status
curl -s http://127.0.0.1:8000/api/v1/health/summary
```

Common problems:

- **Database connection fails:** check `docker compose ps`, port `3307`, and
  `OPSLENS_DATABASE_URL`.
- **AWS profile not found/expired:** run `aws sso login --profile <profile>` in the same user
  account that runs the backend.
- **Chat says key missing:** store it in Settings, or restart the backend from a terminal where
  `ANTHROPIC_API_KEY` is exported.
- **Model not found:** update the model ID under Settings. Model IDs change over time; the adapter
  deliberately does not hard-code an allowlist.
- **MCP timeout:** check AWS SSO first, then raise `OPSLENS_MCP_TOOL_TIMEOUT_SECONDS` if the account
  inventory is genuinely large.
