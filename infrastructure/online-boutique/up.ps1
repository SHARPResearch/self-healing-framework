# Bring up the SHARP live demo cluster: minikube profile "sharp" with Online Boutique,
# kube-prometheus-stack and Chaos Mesh, then forward Prometheus to localhost:9090.
# Idempotent: safe to run again after a reboot (the profile, images and data are kept).
#   powershell -ExecutionPolicy Bypass -File infrastructure/online-boutique/up.ps1
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$profile = "sharp"

Write-Host "1/6 starting minikube profile $profile"
minikube start -p $profile --driver=docker --container-runtime=containerd --cpus=4 --memory=7168 --kubernetes-version=v1.33.1
kubectl config use-context $profile | Out-Null

Write-Host "2/6 kube-prometheus-stack (monitoring)"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>$null | Out-Null
helm repo add chaos-mesh https://charts.chaos-mesh.org 2>$null | Out-Null
helm repo update | Out-Null
helm upgrade --install kube-prom prometheus-community/kube-prometheus-stack `
  --namespace monitoring --create-namespace --version 92.11.0 `
  -f "$here/prometheus-values.yaml" --wait --timeout 15m

Write-Host "3/6 Chaos Mesh (chaos-testing)"
helm upgrade --install chaos-mesh chaos-mesh/chaos-mesh `
  --namespace chaos-testing --create-namespace --version 2.8.5 `
  -f "$here/chaos-mesh-values.yaml" --wait --timeout 10m

Write-Host "4/6 Online Boutique v0.10.7 (online-boutique)"
kubectl create namespace online-boutique --dry-run=client -o yaml | kubectl apply -f - | Out-Null
kubectl apply -n online-boutique -f "$here/kubernetes-manifests.yaml" | Out-Null

Write-Host "5/6 waiting for Online Boutique rollouts"
$deployments = kubectl get deploy -n online-boutique -o jsonpath='{.items[*].metadata.name}'
foreach ($d in $deployments.Split(" ")) {
  kubectl rollout status "deploy/$d" -n online-boutique --timeout=15m
}

Write-Host "6/6 forwarding Prometheus to http://localhost:9090"
$existing = Get-CimInstance Win32_Process -Filter "Name='kubectl.exe'" |
  Where-Object { $_.CommandLine -like "*port-forward*9090*" }
if (-not $existing) {
  Start-Process -WindowStyle Hidden kubectl -ArgumentList @(
    "--context", $profile, "-n", "monitoring", "port-forward", "svc/kube-prom-kube-prometheus-prometheus", "9090:9090")
}
Write-Host "ready. Prometheus: http://localhost:9090   Online Boutique: minikube service frontend-external -n online-boutique -p $profile"
