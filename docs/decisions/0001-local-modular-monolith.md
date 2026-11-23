# ADR 0001: Local modular monolith

## Status

Accepted.

## Decision

Use a local FastAPI modular monolith and a separate local MCP stdio subprocess. Serve the React production bundle from FastAPI later; use Vite during development.

## Consequences

- There is no public application endpoint.
- Module contracts remain testable without microservice deployment overhead.
- MCP tools can be reused by another local MCP host.
- MySQL and AWS remain external runtime dependencies.
