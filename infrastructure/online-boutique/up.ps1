# Bring up the SHARP live demo cluster: minikube profile "sharp" with Online Boutique,
# kube-prometheus-stack (with Grafana), a blackbox exporter probing every service, and Chaos Mesh, then forward Prometheus to localhost:9090
# and Grafana to localhost:3000.
# Idempotent: safe to run again after a reboot (the profile, images and data are kept).
#   powershell -ExecutionPolicy Bypass -File infrastructure/online-boutique/up.ps1
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$profile = "sharp"

Write-Host "1/8 starting minikube profile $profile"
minikube start -p $profile --driver=docker --container-runtime=containerd --cpus=4 --memory=7168 --kubernetes-version=v1.33.1
kubectl config use-context $profile | Out-Null

Write-Host "2/8 kube-prometheus-stack + Grafana (monitoring)"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>$null | Out-Null
helm repo add chaos-mesh https://charts.chaos-mesh.org 2>$null | Out-Null
helm repo update | Out-Null
helm upgrade --install kube-prom prometheus-community/kube-prometheus-stack `
  --namespace monitoring --create-namespace --version 92.11.0 `
  -f "$here/prometheus-values.yaml" --wait --timeout 15m

Write-Host "3/8 Chaos Mesh (chaos-testing)"
helm upgrade --install chaos-mesh chaos-mesh/chaos-mesh `
  --namespace chaos-testing --create-namespace --version 2.8.5 `
  -f "$here/chaos-mesh-values.yaml" --wait --timeout 10m

Write-Host "4/8 blackbox exporter: a response time probe per Online Boutique service (monitoring)"
helm upgrade --install blackbox prometheus-community/prometheus-blackbox-exporter `
  --namespace monitoring --version 11.21.3 `
  -f "$here/blackbox-values.yaml" --wait --timeout 5m

Write-Host "5/8 Online Boutique v0.10.7 (online-boutique)"
kubectl create namespace online-boutique --dry-run=client -o yaml | kubectl apply -f - | Out-Null
kubectl apply -n online-boutique -f "$here/kubernetes-manifests.yaml" | Out-Null

Write-Host "6/8 waiting for Online Boutique rollouts"
$deployments = kubectl get deploy -n online-boutique -o jsonpath='{.items[*].metadata.name}'
foreach ($d in $deployments.Split(" ")) {
  kubectl rollout status "deploy/$d" -n online-boutique --timeout=15m
}

Write-Host "7/8 Grafana dashboard (SHARP Online Boutique)"
kubectl apply -f "$here/grafana-dashboard-sharp.yaml" | Out-Null

Write-Host "8/8 forwarding Prometheus to :9090 and Grafana to :3000"
function Start-Forward($svc, $local, $remote) {
  $existing = Get-CimInstance Win32_Process -Filter "Name='kubectl.exe'" |
    Where-Object { $_.CommandLine -like "*port-forward*$svc*" }
  if (-not $existing) {
    Start-Process -WindowStyle Hidden kubectl -ArgumentList @(
      "--context", $profile, "-n", "monitoring", "port-forward", "svc/$svc", "${local}:${remote}")
  }
}
Start-Forward "kube-prom-kube-prometheus-prometheus" 9090 9090
Start-Forward "kube-prom-grafana" 3000 80
Write-Host "ready."
Write-Host "  Prometheus:      http://localhost:9090"
Write-Host "  Grafana:         http://localhost:3000   (user admin; password: see README, or run the command below)"
Write-Host '    kubectl -n monitoring get secret kube-prom-grafana -o jsonpath="{.data.admin-password}" | % { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_)) }'
Write-Host "  Online Boutique: minikube service frontend-external -n online-boutique -p $profile"
