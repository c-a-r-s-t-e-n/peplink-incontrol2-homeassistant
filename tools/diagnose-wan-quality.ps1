# Read-only, sanitized WAN-quality diagnostics for InControl 2.
# Uses only GET requests for diagnostics; token acquisition uses POST.
# No tokens, coordinates, serial numbers, IPs, cell IDs or device names in output.
param([string]$OutputPath = "$env:USERPROFILE\Desktop\Peplink-WAN-Diagnostics.json")

$ErrorActionPreference = "Stop"
$clientId = Read-Host "InControl 2 Client ID"
$secret = Read-Host "InControl 2 Client Secret" -AsSecureString
try {
  $plainSecret = [System.Net.NetworkCredential]::new("", $secret).Password
  $auth = Invoke-RestMethod -Uri "https://api.ic.peplink.com/api/oauth2/token" -Method Post -Body @{
    grant_type="client_credentials"; client_id=$clientId; client_secret=$plainSecret
  }
} finally {
  Remove-Variable plainSecret -ErrorAction SilentlyContinue
}
if (-not $auth.access_token) { throw "OAuth authentication returned no access token" }
$headers = @{ Authorization = "Bearer $($auth.access_token)" }
$root = "https://api.ic.peplink.com"
$items = [System.Collections.Generic.List[object]]::new()

function Get-Api($path, $query = @{}) {
  $pairs = @()
  foreach ($key in $query.Keys) {
    $pairs += "$([uri]::EscapeDataString($key))=$([uri]::EscapeDataString([string]$query[$key]))"
  }
  $url = $root + $path
  if ($pairs.Count) { $url += "?" + ($pairs -join "&") }
  $result = Invoke-RestMethod -Method Get -Uri $url -Headers $headers
  return $result
}

function Get-SafeValue($sample, $key) {
  if ($null -eq $sample) { return $null }
  $property = $sample.PSObject.Properties[$key]
  if ($null -eq $property) { return $null }
  return $property.Value
}

$orgs = Get-Api "/rest/o"
if ($orgs.resp_code -ne "SUCCESS") { throw "Organization query failed" }
$ordinal = 0
foreach ($org in @($orgs.data)) {
  $groups = Get-Api "/rest/o/$($org.id)/g"
  if ($groups.resp_code -ne "SUCCESS") { continue }
  foreach ($grp in @($groups.data)) {
    $base = "/rest/o/$($org.id)/g/$($grp.id)"
    $routers = Get-Api "$base/d"
    if ($routers.resp_code -ne "SUCCESS") { continue }
    foreach ($router in @($routers.data)) {
      $ordinal++
      $path = "$base/d/$($router.id)"
      $dates = Get-Api "$path/wan_quality/dates"
      $days = @($dates.data | ForEach-Object { $_.day } | Where-Object { $_ -match '^\d{4}-\d{2}-\d{2}$' } | Sort-Object -Descending)
      $day = if ($days.Count) { $days[0] } else { (Get-Date).ToString("yyyy-MM-dd") }
      $start = "$($day)T00:00:00"
      $end = "$($day)T23:59:59"
      $meta = Get-Api "$path/wan_quality" @{ start=$start; end=$end }
      $record = [ordered]@{
        device = "Device_$ordinal"
        dates_response = $dates.resp_code
        available_report_days = $days.Count
        chosen_day = $day
        metadata_response = $meta.resp_code
        wans = @()
      }
      if ($meta.resp_code -eq "SUCCESS") {
        $wanReports = @()
        foreach ($wan in @($meta.data.wans)) {
          if ($null -eq $wan -or $null -eq $wan.id) { continue }
          $report = Get-Api "$path/wan_quality" @{wan_id=[int]$wan.id; start=$start; end=$end}
          $samples = @($report.data.stat | Where-Object { $null -ne $_ })
          $last = $samples | Sort-Object -Property ts -Descending | Select-Object -First 1
          $measurements = [ordered]@{}
          foreach ($field in @("rsrp","rsrq","rssi","sinr","band","bearer","lms","signal","quality")) {
            $measurements[$field] = Get-SafeValue $last $field
          }
          $wanReports += [ordered]@{
            ordinal = $wanReports.Count + 1
            response = $report.resp_code
            sample_count = $samples.Count
            sample_keys = if ($last) { @($last.PSObject.Properties.Name | Sort-Object) } else { @() }
            values = $measurements
            has_carrier = ($null -ne (Get-SafeValue $last "carrier_name"))
            # Never output cid/lcid, network identity, IPs or location.
          }
        }
        $record.wans = $wanReports
      }
      $items.Add([pscustomobject]$record)
    }
  }
}
$output = [ordered]@{ report="Sanitized InControl 2 cellular quality probe"; timestamp_utc=(Get-Date).ToUniversalTime().ToString("o"); results=@($items.ToArray()) }
$output | ConvertTo-Json -Depth 12 | Set-Content -Path $OutputPath -Encoding UTF8
Write-Host "Saved sanitized report to $OutputPath"
