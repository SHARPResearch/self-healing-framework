# Deploy SHARP's ml-backend into the "sharp" minikube cluster with its Helm chart, next to the
# Online Boutique it monitors. Run after up.ps1, ideally once Online Boutique has had an hour of
# untouched traffic (the warm-up window; services/ml-backend/README.md).
#   powershell -ExecutionPolicy Bypass -File infrastructure/online-boutique/deploy-sharp.ps1
#   ... -SkipBuild     reuse the image already loaded into minikube
# Idempotent: a second run upgrades the release. The frontend (pnpm dev) reaches it on :8002.
param([switch]$SkipBuild)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Resolve-Path "$here/../.."
$profile = "sharp"
$namespace = "selfheal-system"
$image = "sharp/ml-backend:dev"

kubectl config use-context $profile | Out-Null

if (-not $SkipBuild) {
  Write-Host "1/4 building $image"
  docker build -f "$root/services/ml-backend/Dockerfile" -t $image $root
  if ($LASTEXITCODE -ne 0) { throw "docker build failed" }
  Write-Host "    loading it into minikube (about 1.5 GB, a minute or two)"
  minikube -p $profile image load $image --overwrite=true
} else {
  Write-Host "1/4 skipping the build"
}

Write-Host "2/4 helm upgrade --install sharp into $namespace"
helm upgrade --install sharp "$root/infrastructure/helm/self-healing-framework" `
  --namespace $namespace --create-namespace --wait=false
# the image tag does not change between local builds, so roll the pod to pick up a new one
kubectl -n $namespace rollout restart deploy/ml-backend | Out-Null

Write-Host "3/4 waiting for TimescaleDB, Redis and the ml-backend pod"
kubectl -n $namespace rollout status statefulset/timescaledb --timeout=5m
kubectl -n $namespace rollout status deploy/redis --timeout=3m
# Wait for the new pod, not the outgoing one (Recreate: a port-forward to a terminating pod dies).
# Ready means warmed up on Prometheus history: seconds when it has an hour of it, longer on a fresh
# cluster (the readiness probe waits; LIVE_MIN_WARMUP_MINUTES is 10).
kubectl -n $namespace rollout status deploy/ml-backend --timeout=20m

Write-Host "4/4 forwarding ml-backend to :8002 (stop any local uvicorn on 8002 first)"
$existing = Get-CimInstance Win32_Process -Filter "Name='kubectl.exe'" |
  Where-Object { $_.CommandLine -like "*port-forward*svc/ml-backend*" }
if ($existing) { $existing | ForEach-Object { Stop-Process -Id $_.ProcessId -Force } }
Start-Process -WindowStyle Hidden kubectl -ArgumentList @(
  "--context", $profile, "-n", $namespace, "port-forward", "svc/ml-backend", "8002:8002")
Write-Host "ready."
Write-Host "  API:        http://localhost:8002/api/ready   (503 until the warm-up finishes)"
Write-Host "  Metrics:    http://localhost:8002/metrics"
Write-Host "  Logs:       kubectl -n $namespace logs deploy/ml-backend -f"
Write-Host "  Dashboard:  cd frontend; pnpm dev   ->  http://localhost:5173/model-lifecycle"
Write-Host "  Grafana:    'SHARP ml-backend: detection and CADAL lifecycle'"
