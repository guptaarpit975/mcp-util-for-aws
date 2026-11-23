# OpsLens — local AWS operations assistant

OpsLens is a laptop-only, read-only AWS operations application. Its React UI, FastAPI API,
MCP client/server, MySQL database, configuration, inventory, conversations, and audit history all
run locally. Anthropic receives prompts and the AWS evidence needed to answer them; AWS and model
credentials are never sent to the browser or stored in MySQL.

Phases 0–5 are implemented:

- local workspace, startup tooling, MySQL migrations, settings, and audit persistence;
- read-only inventory for CloudFront, ALB, S3, ECS/Fargate, RDS, KMS, SES, Parameter Store,
  CloudWatch, ECR, and IAM;
- a local MCP stdio server with typed evidence tools;
- bounded CloudWatch reference-ID search and RDS CloudWatch metrics;
- deterministic health checks and persistent findings;
- a provider-neutral agent loop with an Anthropic adapter, MCP tool calls, SSE status events,
  MySQL conversation history, and a minimal React chat screen.

## Start here

Follow the copy-paste setup and startup instructions in
[docs/runbook.md](docs/runbook.md). The short path is:

```bash
cp .env.example .env
docker compose up -d mysql
uv sync --all-packages --all-extras
pnpm install
uv run --package opslens-api alembic -c backend/alembic.ini upgrade head
make dev
```

Then open [http://127.0.0.1:5173](http://127.0.0.1:5173), configure the AWS profile and model key
under **Settings**, refresh inventory, and use **Ask AI**.

## Documentation

- [Local setup, database, environment variables, and commands](docs/runbook.md)
- [Full architecture, trust boundaries, and request flows](docs/architecture/full-system.md)
- [Architecture decision: local modular monolith](docs/decisions/0001-local-modular-monolith.md)

## Safety boundary

The AWS layer is deliberately read-only. It exposes specific inspection operations—not shell,
arbitrary Python, arbitrary SQL, AWS CLI, secret-value retrieval, cryptographic operations, email
sending, or AWS mutation tools. Use a dedicated read-only IAM Identity Center permission set and
an expected AWS account ID allowlist.
