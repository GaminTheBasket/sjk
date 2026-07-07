# Script gửi sample readings 
$headers = @{
    'Authorization' = 'Bearer local-dev-token'
    'Content-Type' = 'application/json'
}

Write-Host "Sending readings to API..."

# Reading 1
$body1 = @{requestId='test-001'; device_id='SENSOR-A01'; metric='temperature'; value=24.5; unit='celsius'; timestamp='2026-07-06T10:00:00Z'} | ConvertTo-Json
Invoke-WebRequest -Uri "http://localhost:8000/readings" -Method POST -Headers $headers -Body $body1 -UseBasicParsing | Out-Null
Write-Host "✓ Reading 1 sent"

# Reading 2
$body2 = @{requestId='test-002'; device_id='SENSOR-A01'; metric='humidity'; value=65.0; unit='percent'; timestamp='2026-07-06T10:01:00Z'} | ConvertTo-Json
Invoke-WebRequest -Uri "http://localhost:8000/readings" -Method POST -Headers $headers -Body $body2 -UseBasicParsing | Out-Null
Write-Host "✓ Reading 2 sent"

# Reading 3
$body3 = @{requestId='test-003'; device_id='SENSOR-B02'; metric='temperature'; value=22.3; unit='celsius'; timestamp='2026-07-06T10:02:00Z'} | ConvertTo-Json
Invoke-WebRequest -Uri "http://localhost:8000/readings" -Method POST -Headers $headers -Body $body3 -UseBasicParsing | Out-Null
Write-Host "✓ Reading 3 sent"

# Reading 4
$body4 = @{requestId='test-004'; device_id='SENSOR-B02'; metric='humidity'; value=58.0; unit='percent'; timestamp='2026-07-06T10:03:00Z'} | ConvertTo-Json
Invoke-WebRequest -Uri "http://localhost:8000/readings" -Method POST -Headers $headers -Body $body4 -UseBasicParsing | Out-Null
Write-Host "✓ Reading 4 sent"

Write-Host "`nWaiting for Analytics to process..."
Start-Sleep -Seconds 5

Write-Host "Fetching metrics from Core Business..."
$response = Invoke-WebRequest -Uri "http://localhost:8020/analytics/metrics/latest" -UseBasicParsing
$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$filename = "collections/core_business_metrics_$timestamp.json"
$response.Content | Out-File -FilePath $filename -Encoding utf8

Write-Host "✓ Metrics saved to: $filename`n"
Write-Host "--- Metrics Content ---"
$response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10
