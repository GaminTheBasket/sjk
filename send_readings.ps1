# Script gửi sample readings đến API
$headers = @{
    'Authorization' = 'Bearer local-dev-token'
    'Content-Type' = 'application/json'
}

$apiUrl = "http://localhost:8000/readings"

# Tạo 4 readings sample
$readings = @(
    @{requestId='test-001'; device_id='SENSOR-A01'; metric='temperature'; value=24.5; unit='celsius'; timestamp='2026-07-06T10:00:00Z'},
    @{requestId='test-002'; device_id='SENSOR-A01'; metric='humidity'; value=65.0; unit='percent'; timestamp='2026-07-06T10:01:00Z'},
    @{requestId='test-003'; device_id='SENSOR-B02'; metric='temperature'; value=22.3; unit='celsius'; timestamp='2026-07-06T10:02:00Z'},
    @{requestId='test-004'; device_id='SENSOR-B02'; metric='humidity'; value=58.0; unit='percent'; timestamp='2026-07-06T10:03:00Z'}
)

Write-Host "Sending $($readings.Count) readings to API..."
$count = 0

foreach ($reading in $readings) {
    try {
        $response = Invoke-WebRequest -Uri $apiUrl -Method POST -Headers $headers -Body ($reading | ConvertTo-Json) -UseBasicParsing
        $count++
        Write-Host "✓ Sent reading $count : $($reading.device_id) - $($reading.metric) = $($reading.value)"
    } catch {
        Write-Host "✗ Error sending reading: $_"
    }
}

Write-Host "`nWaiting 3 seconds for Analytics to process..."
Start-Sleep -Seconds 3

# Lấy metrics từ Core Business
Write-Host "`nFetching metrics from Core Business..."
$metricsUrl = "http://localhost:8020/analytics/metrics/latest"
try {
    $metrics = Invoke-WebRequest -Uri $metricsUrl -UseBasicParsing
    $timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $filename = "collections/core_business_metrics_$timestamp.json"
    $metrics.Content | Out-File -FilePath $filename -Encoding utf8
    Write-Host "✓ Metrics saved to: $filename"
    Write-Host "`n--- Metrics Content ---"
    $metrics.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10
} catch {
    Write-Host "✗ Error fetching metrics: $_"
}
