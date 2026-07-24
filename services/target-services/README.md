# target-services

Sample microservices used as chaos-injection/demo targets (Doc2 reference tree), not part of the
self-healing framework itself:

- `service-a-auth/` — Node.js Express
- `service-b-orders/` — Python FastAPI (intentionally leaky memory, for demoing recovery)
- `service-c-inventory/` — Go HTTP server

Each gets annotated with `selfheal.io/upstreams` (Doc1 §5) so the Decision Engine can build the
dependency DAG. Not yet scaffolded — see `docs/Doc3_Execution_Guide.md` Phase 4 manual tasks.
