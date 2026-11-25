# Stop the SHARP live demo cluster and the Prometheus, Grafana and ml-backend port-forwards. Nothing is deleted: up.ps1
# starts it again with the same images and Prometheus data. To remove it entirely:
#   minikube delete -p sharp
Get-CimInstance Win32_Process -Filter "Name='kubectl.exe'" |
  Where-Object { $_.CommandLine -like "*port-forward*" -and ($_.CommandLine -like "*kube-prom-kube-prometheus-prometheus*" -or $_.CommandLine -like "*kube-prom-grafana*" -or $_.CommandLine -like "*svc/ml-backend*") } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
minikube stop -p sharp
