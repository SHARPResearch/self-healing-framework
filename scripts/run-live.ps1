# scripts/run-live.ps1
<#
.SYNOPSIS
  One command to run the whole Component 1 + Component 2 + dashboard stack.

.DESCRIPTION
  Starts three processes, prefixes their output into this console, and stops
  all of them on Ctrl+C:

    [C1]  ml-backend          :8002   anomaly detector + model lifecycle + topology
    [C2]  decision-engine     :8000   rule engine, validation, guardrails, executor
    [WEB] frontend            :5173   React dashboard

  Preflight checks run first (Docker, minikube, kubectl namespace, Prometheus
  on :9090, ports free). If the online-boutique namespace is missing, the
  script auto-starts the minikube "sharp" profile and re-runs the project's
  infrastructure/online-boutique/up.ps1 to recreate the stack. Each service
  also writes its full log to .run\*.log.

.PARAMETER Live
  KUBERNETES_DRY_RUN=0 - Component 2 will actually restart/scale pods in the
  cluster. Without it, every execution is recorded as NOT_IMPLEMENTED (dry run).

.PARAMETER NoWeb
  Skip the frontend (useful when only testing the two backends).

.PARAMETER C1Only
  Start Component 1 only.

.PARAMETER NoKill
  Do not auto-kill stale listeners on the target ports during preflight.

.PARAMETER NoClusterStart
  Do not auto-start minikube / run up.ps1 when the namespace is missing.
  The script will warn and continue (Component 2 records actions only).

.PARAMETER MinikubeProfile
  minikube profile to use (default "sharp").

.PARAMETER NoBrowser
  Do not auto-open the dashboard/docs in the default browser.

.PARAMETER Showcase
  After startup, trigger a live Component 1 fault and print the resulting
  Component 2 decision and execution proof for the research panel.

.PARAMETER ShowcaseService
  Service used by -Showcase (default "adservice").

.PARAMETER ShowcaseAction
  Live Component 1 action used by -Showcase (default "cpu_stress").

.PARAMETER ShowcaseWaitSec
  How long -Showcase waits for a fresh decision/execution (default 60).

.EXAMPLE
  pwsh -ExecutionPolicy Bypass -File scripts/run-live.ps1
  pwsh -ExecutionPolicy Bypass -File scripts/run-live.ps1 -Live
  pwsh -ExecutionPolicy Bypass -File scripts/run-live.ps1 -Live -Showcase
#>
[CmdletBinding()]
param(
  [switch]$Live,
  [switch]$NoWeb,
  [switch]$C1Only,
  [switch]$NoKill,
  [switch]$NoClusterStart,
  [switch]$NoBrowser,
  [switch]$Showcase,
  [string]$ShowcaseService = "adservice",
  [string]$ShowcaseAction = "cpu_stress",
  [int]$ShowcaseWaitSec = 60,
  [string]$Namespace = "online-boutique",
  [string]$MinikubeProfile = "sharp",
  [int]$C1Port = 8002,
  [int]$C2Port = 8000,
  [int]$WebPort = 5173
)

$ErrorActionPreference = "Stop"
$root   = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root ".run"
$dryRun = if ($Live) { "0" } else { "1" }

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    OK   $msg" -ForegroundColor Green }
function Write-Warn2($msg){ Write-Host "    WARN $msg" -ForegroundColor Yellow }
function Write-Bad($msg)  { Write-Host "    FAIL $msg" -ForegroundColor Red }

function Open-Url([string]$Url, [string]$Label) {
  if ($NoBrowser) { return }
  try {
    Start-Process $Url
    Write-Ok "$Label opened in browser: $Url"
  } catch {
    Write-Warn2 "could not open $Label automatically ($Url): $($_.Exception.Message)"
  }
}

function Resolve-Exe([string]$name) {
  foreach ($ext in @("exe", "cmd", "bat", "ps1")) {
    $c = Get-Command "$name.$ext" -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
  }
  $c = Get-Command $name -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  return $null
}

# -- preflight --------------------------------------------------------
Write-Step "Preflight"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# -- Docker check -----------------------------------------------------
$docker = Resolve-Exe "docker"
if (-not $docker) {
  Write-Bad "docker not found on PATH - minikube's docker driver needs Docker Desktop."
  Write-Host "           Install Docker Desktop and start it, then re-run." -ForegroundColor DarkGray
  exit 1
}
$dockerInfo = & $docker info --format '{{.ServerVersion}}' 2>$null
if (-not $dockerInfo) {
  Write-Bad "Docker daemon is not running. Start Docker Desktop and re-run."
  exit 1
}
Write-Ok "docker: $docker (daemon $dockerInfo)"

# -- uv check ---------------------------------------------------------
$uv = Resolve-Exe "uv"
if (-not $uv) { Write-Bad "uv not found on PATH (needed for both Python services)"; exit 1 }
Write-Ok "uv: $uv"

if (-not $NoWeb -and -not $C1Only) {
  $pnpm = Resolve-Exe "pnpm"
  if (-not $pnpm) { Write-Bad "pnpm not found on PATH (needed for the frontend)"; exit 1 }
  Write-Ok "pnpm: $pnpm"
}

# -- ports check (auto-kill stale listeners unless -NoKill) -----------
$targetPorts = @($C1Port, $C2Port) + $(if ($NoWeb -or $C1Only) { @() } else { @($WebPort) })

foreach ($p in $targetPorts) {
  $busy = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
  if ($busy) {
    $pids = $busy | Select-Object -ExpandProperty OwningProcess -Unique
    if ($NoKill) {
      Write-Bad "port $p is already in use (PID $($pids -join ', ')). Re-run without -NoKill or kill manually."
      exit 1
    }
    Write-Warn2 "port $p busy (PID $($pids -join ', ')) - killing stale listener(s)"
    foreach ($pid_ in $pids) {
      try { Stop-Process -Id $pid_ -Force -ErrorAction Stop } catch { Write-Warn2 "could not kill PID $pid_" }
    }
    Start-Sleep -Milliseconds 400
    if (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) {
      Write-Bad "port $p is still in use after kill attempt"
      exit 1
    }
  }
}
Write-Ok "ports $($targetPorts -join ', ') are free"

# -- Kubernetes / minikube / online-boutique check --------------------
function Test-Namespace {
  param([string]$ns)
  if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) { return $false }
  $out = kubectl get namespace $ns -o name 2>$null
  return [bool]$out
}

function Ensure-Cluster {
  param([string]$ns, [string]$profile, [switch]$SkipStart)

  if (Test-Namespace $ns) {
    Write-Ok "kubernetes namespace '$ns' exists"
    return $true
  }

  # Namespace missing. If the user asked us not to start anything, warn and stop here.
  if ($SkipStart) {
    Write-Warn2 "namespace '$ns' not found - Component 2 will record actions but nothing will run"
    Write-Host "           (skipped auto-start because -NoClusterStart was passed)" -ForegroundColor DarkGray
    return $false
  }

  Write-Warn2 "namespace '$ns' not found - attempting to start minikube profile '$profile'"

  # 1. minikube must exist
  $mk = Resolve-Exe "minikube"
  if (-not $mk) {
    Write-Bad "minikube not found on PATH - install it, or run 'up.ps1' manually, or pass -NoClusterStart"
    return $false
  }

  # 2. profile must exist in 'minikube profile list'
  $profilesOut = & $mk profile list 2>$null | Out-String
  if ($profilesOut -notmatch [regex]::Escape($profile)) {
    Write-Bad "minikube profile '$profile' does not exist."
    Write-Host "           Create it with: powershell -ExecutionPolicy Bypass -File infrastructure/online-boutique/up.ps1" -ForegroundColor DarkGray
    return $false
  }

  # 3. bring the profile up
  Write-Step "Starting minikube profile '$profile'"
  & $mk -p $profile start
  if ($LASTEXITCODE -ne 0) {
    Write-Bad "minikube start -p $profile failed (exit $LASTEXITCODE)"
    return $false
  }

  # 4. point kubectl at the profile
  Write-Step "Switching kubectl context to '$profile'"
  & kubectl config use-context $profile | Out-Null
  if ($LASTEXITCODE -ne 0) {
    Write-Bad "kubectl config use-context $profile failed"
    return $false
  }

  # 5. re-check the namespace after start (it may already exist in the profile)
  if (Test-Namespace $ns) {
    Write-Ok "kubernetes namespace '$ns' exists (after minikube start)"
    return $true
  }

  # 6. namespace still missing -> run the project's up.ps1 to recreate the stack
  $upScript = Join-Path $root "infrastructure/online-boutique/up.ps1"
  if (-not (Test-Path $upScript)) {
    Write-Bad "namespace '$ns' still missing and $upScript not found"
    return $false
  }

  Write-Step "Recreating '$ns' via $upScript (this installs Prometheus, Chaos Mesh, Online Boutique - can take several minutes)"
  & powershell -ExecutionPolicy Bypass -File $upScript
  if ($LASTEXITCODE -ne 0) {
    Write-Bad "up.ps1 failed (exit $LASTEXITCODE)"
    return $false
  }

  # 7. final verify
  if (Test-Namespace $ns) {
    Write-Ok "kubernetes namespace '$ns' exists (after up.ps1)"
    return $true
  }
  Write-Bad "namespace '$ns' still not present after up.ps1 - aborting"
  return $false
}

$clusterOk = Ensure-Cluster -ns $Namespace -profile $MinikubeProfile -SkipStart:$NoClusterStart


# -- Prometheus check and automatic port-forward -----------------------
$script:promPortForward = $null

if ($clusterOk) {
  $promUrl = "http://localhost:9090/-/ready"
  $promService = "kube-prom-kube-prometheus-prometheus"

  # First check whether Prometheus is already accessible.
  $promReady = $false

  try {
    $r = Invoke-WebRequest $promUrl -TimeoutSec 3 -UseBasicParsing
    $promReady = ($r.StatusCode -eq 200)
  } catch {}

  if ($promReady) {
    Write-Ok "Prometheus already reachable on :9090"
  } else {
    Write-Step "Starting Prometheus port-forward"

    $kubectl = Resolve-Exe "kubectl"

    if (-not $kubectl) {
      Write-Bad "kubectl not found"
      exit 1
    }

    # Verify the actual service exists.
    $service = & $kubectl get svc $promService -n monitoring -o name 2>$null

    if (-not $service) {
      Write-Bad "Prometheus service '$promService' not found in monitoring namespace"
      exit 1
    }

    $pfOut = Join-Path $logDir "PROMETHEUS.log"
    $pfErr = Join-Path $logDir "PROMETHEUS.err.log"

    "" | Set-Content $pfOut
    "" | Set-Content $pfErr

    # Do not take over an unrelated listener on port 9090.
    $listener = Get-NetTCPConnection -LocalPort 9090 -State Listen `
      -ErrorAction SilentlyContinue

    if ($listener) {
      Write-Bad "Port 9090 is occupied, but Prometheus is not responding. Check the existing listener."
      exit 1
    }

    $script:promPortForward = Start-Process `
      -FilePath $kubectl `
      -ArgumentList @(
        "port-forward",
        "-n", "monitoring",
        "svc/$promService",
        "9090:9090"
      ) `
      -RedirectStandardOutput $pfOut `
      -RedirectStandardError $pfErr `
      -PassThru `
      -WindowStyle Hidden

    # Wait for Prometheus to become ready.
    $deadline = (Get-Date).AddSeconds(30)

    while ((Get-Date) -lt $deadline) {
      if ($script:promPortForward.HasExited) {
        Write-Bad "Prometheus port-forward exited unexpectedly."
        Get-Content $pfErr -ErrorAction SilentlyContinue |
          Write-Host
        exit 1
      }

      try {
        $r = Invoke-WebRequest $promUrl -TimeoutSec 2 -UseBasicParsing
        if ($r.StatusCode -eq 200) {
          $promReady = $true
          break
        }
      } catch {}

      Start-Sleep -Milliseconds 700
    }

    if (-not $promReady) {
      Write-Bad "Prometheus did not become ready within 30 seconds."
      Write-Host "Check .run\PROMETHEUS.err.log"
      exit 1
    }

    Write-Ok "Prometheus port-forward started and ready on :9090"
  }
}

# -- process launcher -------------------------------------------------
$script:procs = @()

function Start-Svc {
  param([string]$Name, [string]$Dir, [string]$Exe, [string[]]$ArgList, [hashtable]$EnvVars)

  $saved = @{}
  foreach ($k in $EnvVars.Keys) {
    $saved[$k] = [Environment]::GetEnvironmentVariable($k, "Process")
    [Environment]::SetEnvironmentVariable($k, $EnvVars[$k], "Process")
  }

  $out = Join-Path $logDir "$Name.log"
  $err = Join-Path $logDir "$Name.err.log"
  "" | Set-Content $out
  "" | Set-Content $err

  $ext = [System.IO.Path]::GetExtension($Exe).ToLowerInvariant()
  if ($ext -in @(".ps1", ".cmd", ".bat")) {
    $launchExe  = "cmd.exe"
    $launchArgs = @("/c", $Exe) + $ArgList
  } else {
    $launchExe  = $Exe
    $launchArgs = $ArgList
  }

  $p = Start-Process -FilePath $launchExe -ArgumentList $launchArgs -WorkingDirectory $Dir `
    -RedirectStandardOutput $out -RedirectStandardError $err -PassThru -WindowStyle Hidden

  foreach ($k in $saved.Keys) { [Environment]::SetEnvironmentVariable($k, $saved[$k], "Process") }

  $script:procs += [pscustomobject]@{ Name = $Name; Proc = $p; Out = $out; Err = $err; Offset = 0; ErrOffset = 0 }
  Write-Ok "$Name started (PID $($p.Id)) -> $out"
}

function Wait-Http {
  param([string]$Url, [int]$Seconds = 90)
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    try { if ((Invoke-WebRequest $Url -TimeoutSec 2 -UseBasicParsing).StatusCode -eq 200) { return $true } } catch { }
    Start-Sleep -Milliseconds 800
  }
  return $false
}

function Invoke-JsonGet {
  param([string]$Url)
  try { return Invoke-RestMethod $Url -TimeoutSec 5 -UseBasicParsing }
  catch { return $null }
}

function Get-ApiItems {
  param($Response, [string]$Key)
  if ($null -eq $Response) { return @() }
  $prop = $Response.PSObject.Properties[$Key]
  if ($null -ne $prop) { return @($prop.Value) }
  if ($Response -is [System.Array]) { return @($Response) }
  return @()
}

function Show-ResearchShowcase {
  Write-Step "Research showcase: live fault -> decision -> execution"
  if (-not $Live) {
    Write-Warn2 "running in dry-run mode: decisions will appear, execution will be recorded as NOT_IMPLEMENTED"
  }

  $decBase = @(Get-ApiItems (Invoke-JsonGet "http://localhost:$C2Port/api/decisions/recent?limit=100") "decisions" |
    ForEach-Object { $_.decision_id })
  $execBase = @(Get-ApiItems (Invoke-JsonGet "http://localhost:$C2Port/api/executions?limit=100") "executions" |
    ForEach-Object { $_.decision_id })

  try {
    $fault = Invoke-RestMethod -Method Post `
      -Uri "http://localhost:$C1Port/api/live/$ShowcaseService/$ShowcaseAction" `
      -TimeoutSec 20 -UseBasicParsing
    Write-Ok "C1 fault triggered: $ShowcaseAction on $ShowcaseService -> $($fault | ConvertTo-Json -Depth 5 -Compress)"
  } catch {
    Write-Bad "C1 fault trigger failed: $($_.Exception.Message)"
    return
  }

  $deadline = (Get-Date).AddSeconds($ShowcaseWaitSec)
  $freshDecisions = @()
  while ((Get-Date) -lt $deadline) {
    $allDecisions = @(Get-ApiItems (Invoke-JsonGet "http://localhost:$C2Port/api/decisions/recent?limit=100") "decisions")
    $freshDecisions = @($allDecisions | Where-Object { $_.decision_id -and $_.decision_id -notin $decBase })
    if ($freshDecisions.Count -gt 0) { break }
    Start-Sleep -Seconds 2
  }

  if ($freshDecisions.Count -eq 0) {
    Write-Bad "No fresh C2 decision appeared within ${ShowcaseWaitSec}s - check .run\C1.log and .run\C2.log"
    return
  }

  $d = $freshDecisions[0]
  $outcome = if ($d.policy) { $d.policy.outcome } else { "-" }
  $reason = if ($d.policy) { $d.policy.reason } else { "-" }
  $conf = if ($d.confidence) { $d.confidence.final } else { "-" }

  Write-Host ""
  Write-Host "  FRESH DECISION PROOF" -ForegroundColor Green
  $d | Select-Object decision_id, anomaly_id, rule_id, action | Format-List | Out-Host
  Write-Host "    policy_outcome : $outcome" -ForegroundColor Yellow
  Write-Host "    policy_reason  : $reason" -ForegroundColor Yellow
  Write-Host "    confidence     : $conf" -ForegroundColor Yellow

  $deadline = (Get-Date).AddSeconds($ShowcaseWaitSec)
  $freshExecutions = @()
  while ((Get-Date) -lt $deadline -and $outcome -eq "AUTO_EXECUTE") {
    $allExecutions = @(Get-ApiItems (Invoke-JsonGet "http://localhost:$C2Port/api/executions?limit=100") "executions")
    $freshExecutions = @($allExecutions | Where-Object {
      $_.decision_id -eq $d.decision_id -and $_.decision_id -notin $execBase
    })
    if ($freshExecutions.Count -gt 0) { break }
    Start-Sleep -Seconds 2
  }

  if ($freshExecutions.Count -gt 0) {
    Write-Host "  EXECUTION PROOF" -ForegroundColor Green
    $freshExecutions[0] | ConvertTo-Json -Depth 6 | Write-Host
  } elseif ($outcome -eq "AUTO_EXECUTE") {
    Write-Warn2 "Decision was AUTO_EXECUTE but no execution row appeared yet - check .run\C2.log"
  } else {
    Write-Warn2 "No execution expected: policy outcome was $outcome"
  }
}

# -- start ------------------------------------------------------------
Write-Step "Starting Component 1 (ml-backend, live mode)"
Start-Svc -Name "C1" -Dir (Join-Path $root "services/ml-backend") -Exe $uv `
  -ArgList @("run", "uvicorn", "app.main:app", "--port", "$C1Port") `
  -EnvVars @{
    TELEMETRY_MODE      = "prometheus"
    PROMETHEUS_URL      = "http://localhost:9090"
    K8S_NAMESPACE       = $Namespace
    TELEMETRY_NAMESPACE = $Namespace
  }

if (Wait-Http "http://localhost:$C1Port/api/health" 90) {
  Write-Ok "Component 1 healthy: http://localhost:$C1Port/api/health"
} else {
  Write-Warn2 "Component 1 did not answer yet - check $logDir\C1.log and C1.err.log"
}

if ($C1Only) {
  Open-Url "http://localhost:$C1Port/docs" "C1 docs"
  Write-Step "C1Only: leaving Component 1 running"
  exit 0
}

Write-Step "Starting Component 2 (decision engine, dry-run=$(-not $Live))"
Start-Svc -Name "C2" -Dir (Join-Path $root "services/decision-engine") -Exe $uv `
  -ArgList @("run", "uvicorn", "app.main:app", "--port", "$C2Port") `
  -EnvVars @{
    COMPONENT1_URL       = "http://localhost:$C1Port"
    KUBERNETES_NAMESPACE = $Namespace
    KUBERNETES_DRY_RUN   = $dryRun
    TELEMETRY_SOURCE_URL = "http://localhost:$C2Port"
    OPEN_DOCS            = "0"
  }

if (Wait-Http "http://localhost:$C2Port/health" 90) {
  Write-Ok "Component 2 healthy: http://localhost:$C2Port/health"
} else {
  Write-Warn2 "Component 2 did not answer yet - check $logDir\C2.log and C2.err.log"
}

if (-not $NoWeb) {
  Write-Step "Starting dashboard (frontend)"
  $pnpmPath = Resolve-Exe "pnpm"
  Start-Svc -Name "WEB" -Dir (Join-Path $root "frontend") -Exe $pnpmPath `
    -ArgList @("dev", "--port", "$WebPort") -EnvVars @{}
  Wait-Http "http://localhost:$WebPort" 30 | Out-Null
  Open-Url "http://localhost:$WebPort" "dashboard"
}

Open-Url "http://localhost:$C1Port/docs" "C1 docs"
Open-Url "http://localhost:$C2Port/docs" "C2 docs"
Open-Url "http://localhost:9090" "Prometheus"

if ($Showcase) { Show-ResearchShowcase }

# -- tail -------------------------------------------------------------
Write-Host ""
Write-Host "===============================================================" -ForegroundColor DarkGray
Write-Host " C1  http://localhost:$C1Port/docs   (anomaly + model lifecycle)" -ForegroundColor Cyan
Write-Host " C2  http://localhost:$C2Port/docs   (decisions + escalations)"  -ForegroundColor Cyan
if (-not $NoWeb) { Write-Host " WEB http://localhost:$WebPort        (dashboard)" -ForegroundColor Cyan }
Write-Host " Execution mode: $(if ($Live) { 'LIVE - actions hit the cluster' } else { 'DRY RUN - actions recorded only' })" -ForegroundColor Yellow
Write-Host "  Prometheus  http://localhost:9090" -ForegroundColor Cyan
Write-Host "              (metrics + PromQL queries)" -ForegroundColor DarkGray
Write-Host " Press Ctrl+C to stop everything." -ForegroundColor DarkGray
Write-Host "===============================================================" -ForegroundColor DarkGray

$colors = @{ C1 = "Magenta"; C2 = "Cyan"; WEB = "Green" }

function Read-New([string]$path, [ref]$offset, [string]$tag, [string]$colour) {
  if (-not (Test-Path $path)) { return }
  $fs = $null; $reader = $null
  try {
    $fs = [System.IO.File]::Open($path, "Open", "Read", "ReadWrite")
    $null = $fs.Seek($offset.Value, "Begin")
    $reader = New-Object System.IO.StreamReader($fs)
    while (-not $reader.EndOfStream) {
      $line = $reader.ReadLine()
      if ($line) { Write-Host "[$tag] " -ForegroundColor $colour -NoNewline; Write-Host $line }
    }
    $offset.Value = $fs.Position
  } catch { } finally {
    if ($reader) { $reader.Dispose() }
    if ($fs)     { $fs.Dispose() }
  }
}

try {
  while ($true) {
    foreach ($svc in $script:procs) {
      $c = $colors[$svc.Name]
      Read-New $svc.Out ([ref]$svc.Offset)    $svc.Name $c
      Read-New $svc.Err ([ref]$svc.ErrOffset) $svc.Name $c
    }

    $alive = $script:procs | Where-Object { -not $_.Proc.HasExited }
    if (-not $alive) { Write-Host "`nAll services exited." -ForegroundColor Yellow; break }
    Start-Sleep -Milliseconds 400
  }
} finally {
  Write-Host "`nStopping services..." -ForegroundColor Yellow
  foreach ($svc in $script:procs) {
    if (-not $svc.Proc.HasExited) {
      try { Stop-Process -Id $svc.Proc.Id -Force -ErrorAction SilentlyContinue } catch { }
    }
  }
  foreach ($p in @($C1Port, $C2Port, $WebPort)) {
    Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue |
      ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
  }
  Write-Host "Stopped. Logs in $logDir" -ForegroundColor DarkGray
}