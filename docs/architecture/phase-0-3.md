# Phase 0–3 architecture (historical)

For the current Phase 0–5 architecture, see [full-system.md](full-system.md).

OpsLens is a local modular monolith with two Python runtime processes and an optional Vite development process.

## Runtime boundaries

1. `opslens-api` serves the local REST API, settings, MySQL repositories, AWS inventory workflows, and MCP client.
2. `aws-ops-mcp` is launched by the API as a local stdio subprocess and exposes read-only AWS tools.
3. The React application calls only the FastAPI process on localhost.
4. MySQL stores configuration, inventory, audit records, and the future conversation model.

## Trust boundaries

- AWS credentials remain in the AWS SDK credential chain and are not persisted by OpsLens.
- Model-provider keys are referenced through the operating-system keychain.
- The frontend never receives AWS or model-provider credentials.
- The MCP subprocess receives the selected AWS profile explicitly from the backend.
- MCP tools do not expose arbitrary commands or mutation operations.

## Phase boundaries

- Phase 0: repository, tooling, local startup, documentation.
- Phase 1: MySQL models, migrations, settings, keychain references, diagnostics.
- Phase 2: STS validation, normalized resource inventory, React resource view.
- Phase 3: MCP stdio server, client diagnostics, initial service tools.

Phases 4–5 now implement health findings and the provider-neutral agent loop described in the
current architecture document.
