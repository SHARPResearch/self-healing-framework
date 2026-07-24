# infrastructure

Helm charts, Kubernetes manifests, and Terraform (Doc1 §8 deployment topology, Doc2 reference tree).

**Status**: skeleton only — `Chart.yaml`/`values.yaml` exist but templates are empty (`.gitkeep`),
`kubernetes/namespaces.yaml` is real (three namespaces: `selfheal-system`, `selfheal-apps`,
`selfheal-frontend`), `rbac/`/`network-policies/`/`terraform/` are placeholders.

**Build next** (`docs/Doc3_Execution_Guide.md` Phase 8-9, in order):
1. `helm/self-healing-framework/templates/{ml-backend,decision-engine,yarp-gateway}/` —
   `deployment.yaml`, `service.yaml`, `configmap.yaml`/`hpa.yaml`/`rbac.yaml` as applicable
2. `helm/self-healing-framework/templates/redis/` — StatefulSet + PVC
3. `helm/self-healing-framework/templates/mlflow/` — Deployment + MinIO StatefulSet
4. `helm/self-healing-framework/templates/monitoring/` — kube-prometheus-stack values override +
   `grafana-dashboards/*.json`
5. `helm/self-healing-framework/templates/chaos-mesh/` — example chaos experiments
   (network-delay, pod-kill, memory-stress)
6. `kubernetes/rbac/decision-engine-sa.yaml` + `cluster-role-binding.yaml` — needed before
   `services/decision-engine` can call the Kubernetes API
7. `kubernetes/network-policies/{deny-all-default,allow-selfheal-system}.yaml`

Do not add `.github/workflows/*.yml` referencing these Helm templates until the services being
deployed actually build — see root `CLAUDE.md`.
