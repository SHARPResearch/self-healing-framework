# Stop the SHARP live demo cluster and the Prometheus port-forward. Nothing is deleted: up.ps1
# starts it again with the same images and Prometheus data. To remove it entirely:
#   minikube delete -p sharp
Get-CimInstance Win32_Process -Filter "Name='kubectl.exe'" |
  Where-Object { $_.CommandLine -like "*port-forward*9090*" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
minikube stop -p sharp
