# infrastructure

Helm charts, Kubernetes manifests, and Terraform for the self-healing framework
(docs/Doc2_GitHub_Monorepo_Structure.md layout).

- `helm/self-healing-framework/` — chart covering ml-backend, decision-engine, yarp-gateway,
  redis, mlflow, and monitoring (Prometheus/Grafana dashboards live under
  `templates/monitoring/`, not as standalone folders).
- `kubernetes/` — `namespaces.yaml`, RBAC, and network policies applied directly (not templated).
- `terraform/` — optional cluster provisioning (EKS/GKE).

See `CLAUDE.md` in this folder and `docs/Doc3_Execution_Guide.md` Phase 8 for what to build next.
