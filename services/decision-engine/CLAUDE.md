# services/decision-engine

.NET 8 Worker Service owning policy evaluation, the service dependency graph, and remediation
action dispatch (Doc1 §2 "Decision Engine", §5 "Dependency-Aware Policy").

**Tech**: .NET 8, `StackExchange.Redis`, `KubernetesClient`, `Yarp.ReverseProxy` (client side, to
call `services/yarp-gateway`'s admin API).

**Status**: scaffold only (`.gitkeep`). No `.sln`/`.csproj` yet.

**Key design point**: the dependency graph is built purely from Kubernetes — it reads the
`selfheal.io/upstreams` annotation on each Deployment in `selfheal-apps`, refreshed every 60s.
No Consul or other service registry.

**Build next** (`docs/Doc3_Execution_Guide.md` Phase 1 & 4, in order):
1. `dotnet new worker -n DecisionEngine` + add `StackExchange.Redis`, `KubernetesClient`,
   `Yarp.ReverseProxy`, `Microsoft.Extensions.Http`
2. `Engine/DependencyGraph.cs` — adjacency list, `RefreshFromKubernetesAsync`, `GetAffectedServices`
3. `Engine/PolicyEvaluator.cs` — `< 0.5` watch, `0.5-0.7` warn, `0.7-0.85` degrade, `> 0.85` critical
4. `Engine/ActionDispatcher.cs` + `Executors/{YarpTrafficShifter,KubernetesExecutor}.cs`
5. `Workers/AnomalyConsumerWorker.cs` — `XREADGROUP` consumer on Redis Streams `anomaly_events`
6. Integration test: mock `AnomalyEvent` via Redis, verify `ActionReceipt` published

Requires RBAC applied first: `infrastructure/kubernetes/rbac/` (ServiceAccount with
`get`/`patch` on Deployments, `delete` on Pods).
