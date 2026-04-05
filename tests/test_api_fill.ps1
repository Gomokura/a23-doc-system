$payload = @{
    template_file_id = '69eb3c13-8fdc-4e12-a461-92da0b1c5dbf'
    source_file_ids = @('ddd271d7-6021-460f-a815-0871f4de75e6')
    max_rows = 5
} | ConvertTo-Json

Write-Host "Sending POST /fill ..."
try {
    $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/fill' -Method POST -ContentType 'application/json' -Body $payload -TimeoutSec 120
    Write-Host "SUCCESS"
    Write-Host "output_file_id: $($r.output_file_id)"
    Write-Host "download_url: $($r.download_url)"

    $dlUrl = "http://127.0.0.1:8000$($r.download_url)"
    Write-Host "Downloading from: $dlUrl"
    Invoke-WebRequest -Uri $dlUrl -OutFile "D:\result_api.xlsx" -TimeoutSec 30
    Write-Host "File saved to D:\result_api.xlsx"
} catch {
    Write-Host "ERROR: $($_.Exception.Message)"
    if ($_.ErrorDetails) { Write-Host "Details: $($_.ErrorDetails.Message)" }
}
