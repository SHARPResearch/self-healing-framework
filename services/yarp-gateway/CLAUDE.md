# services/yarp-gateway

YARP reverse proxy — the execution layer for traffic-shifting recovery (Doc1 §1, §5). Achieves
graceful traffic drain (weight → 0 on a failing pod) without killing it, so in-flight requests
complete.

**Tech**: .NET 8, `Yarp.ReverseProxy`.

**Status**: not yet scaffolded.

**Build next** (`docs/Doc3_Execution_Guide.md` Phase 1 & 5, in order):
1. `dotnet new web -n YarpGateway` + `dotnet add package Yarp.ReverseProxy`
2. `appsettings.json` — static routes/clusters config
3. `Configuration/DynamicRouteProvider.cs` — implements `IProxyConfigProvider`, holds an
   `InMemoryProxyConfig`, exposes `PatchWeight(clusterId, destinationId, weight)`
4. `Controllers/AdminController.cs` — `PATCH /admin/cluster`, bound to `localhost` only
   (the Decision Engine is co-deployed in the same pod and is the only caller)

No file I/O — all config patches are in-memory for zero-downtime updates.
