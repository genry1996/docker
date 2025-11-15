# ================================
#  Restore Grafana dashboards
# ================================

$grafanaContainer = "grafana_inforadar"

$dashboardsHost = "D:\Inforadar_Pro\grafana\dashboards"
$datasourcesHost = "D:\Inforadar_Pro\grafana\provisioning\datasources"
$dashProvHost = "D:\Inforadar_Pro\grafana\provisioning\dashboards"

Write-Host "🔄 Copying dashboards..."
docker cp "$dashboardsHost\." ${grafanaContainer}:/var/lib/grafana/dashboards/

Write-Host "🔄 Copying provisioning dashboards..."
docker cp "$dashProvHost\." ${grafanaContainer}:/etc/grafana/provisioning/dashboards/

Write-Host "🔄 Copying datasources..."
docker cp "$datasourcesHost\." ${grafanaContainer}:/etc/grafana/provisioning/datasources/

Write-Host "🔄 Restarting Grafana..."
docker restart ${grafanaContainer}

Write-Host "✅ Grafana restored successfully!"
