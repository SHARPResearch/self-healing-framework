# infrastructure

Helm charts, Kubernetes manifests, and Terraform for the self-healing framework
(docs/Doc2_GitHub_Monorepo_Structure.md layout).

- `helm/self-healing-framework/`: our own chart. It renders ml-backend (the anomaly detector and the
  CADAL model lifecycle) with TimescaleDB, Redis, a Role on the monitored namespace, a
  ServiceMonitor for its `/metrics` and a Grafana dashboard (`templates/monitoring/`). The
  decision-engine, yarp-gateway and mlflow folders are placeholders for their owners.
  `helm lint --strict` runs in CI.
- `online-boutique/`: the live cluster on minikube.
  - `up.ps1`: minikube, kube-prometheus-stack with Grafana, a blackbox exporter probing every
    service, Chaos Mesh, Online Boutique v0.10.7 and the port-forwards.
  - `deploy-sharp.ps1`: builds the ml-backend image, loads it into minikube and installs the chart
    into `selfheal-system`.
  - `down.ps1`: stops it all, keeping images and data.
  - `*-values.yaml` and `grafana-dashboard-sharp.yaml`: the monitoring configuration.
- `local/`: the Docker Compose stack (TimescaleDB, Redis) for the replay demo on the laptop.
- `kubernetes/`: `namespaces.yaml`, RBAC and network policies applied directly (not templated).
- `terraform/`: optional cluster provisioning (EKS/GKE), not written.

Decision records for the deployment: `docs/adr/0009` to `0013`.
