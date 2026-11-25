# 0015. Tenancy: one runtime per organization, and the organization id on every row

Date: 2026-11-22. Status: Accepted.

## Context
With accounts (0014), several organizations use one SHARP instance. An organization must never
see or affect another's services, models, decisions, operator questions or logs. ml-backend held
one global fleet, one store and one event channel, and every table was keyed by service id
alone; two organizations with a service of the same name would have overwritten each other's
checkpoints and model versions.

## Decision
- **A Runtime per organization** (`app/tenancy.py`). Each request is resolved from its JWT to its
  organization's Runtime: its own fleet, a store bound to its `tenant_id`, its own Redis channel
  (`ws:anomaly_broadcast:<org>`), and metric series labelled `tenant`. Handlers receive that
  Runtime; there is no global one to reach by mistake.
- **Every table has `tenant_id`, part of every key** (`infrastructure/local/init.sql`, migrated
  in place). Store writes always set it and every query filters on it; organizations share one
  connection pool.
- **Which organizations get a fleet.** Replay (the hosted demo): each organization gets its own
  demo fleet, built on first use, at most `MAX_TENANTS` (each fleet holds models and SMD windows
  in memory). Live: the cluster belongs to one organization, `PRIMARY_TENANT`; others are told
  they have no fleet here.
- Only the platform's runtime collects the backend's own logs and the container logs; a tenant
  runtime holds only its lifecycle.

## Alternatives considered
- **A deployment per organization.** Strongest isolation, but on a free plan one organization
  per instance is all there is, and it multiplies databases and secrets.
- **One shared fleet, filtered by organization.** Rejected: CADAL's state is per service, so
  every service would still need an owner, and one organization's demo injections or resets
  would change what another sees.
- **PostgreSQL row-level security.** Worth adding as defence in depth on a shared database; the
  store already scopes every statement, and a test checks two tenants on one pool cannot read
  each other's rows.

## Consequences
Memory grows with organizations: about 260 MB for the first replay fleet and about 40 MB for each
further one, after storing each replay window as one array instead of row dictionaries. The
`anomaly_events` stream carries a `tenant_id` field, so a consumer (the decision engine) can act
per organization. With `AUTH_MODE=off` everything runs as tenant `default`, unchanged.
