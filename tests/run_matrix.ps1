param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,
    [int]$ParallelRequests = 20
)

function Get-StatusCode([scriptblock]$Request) {
    try {
        & $Request
    } catch {
        if ($_.Exception.Response) {
            [int]$_.Exception.Response.StatusCode
        } else {
            0
        }
    }
}

function Get-ParallelStatusCodes([string]$Url, [int]$Count) {
    $jobs = 1..$Count | ForEach-Object {
        Start-Job -ArgumentList $Url -ScriptBlock {
            param($RequestUrl)
            try { (Invoke-WebRequest $RequestUrl -UseBasicParsing -TimeoutSec 10).StatusCode }
            catch { if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { 0 } }
        }
    }
    Wait-Job $jobs | Out-Null
    $result = $jobs | Receive-Job
    Remove-Job $jobs -Force
    return $result
}

Write-Host "Sequential limit test"
$sequential = 1..6 | ForEach-Object {
    Get-StatusCode { (Invoke-WebRequest "$BaseUrl/limited" -UseBasicParsing).StatusCode }
}
$sequential -join ", "

Write-Host "Parallel limit test"
$parallel = Get-ParallelStatusCodes "$BaseUrl/limited" $ParallelRequests
$parallel | Group-Object | Sort-Object Name | ForEach-Object {
    "$($_.Name)=$($_.Count)"
}

Write-Host "X-Forwarded-For test"
$forwarded = 1..5 | ForEach-Object {
    Get-StatusCode {
        (Invoke-WebRequest "$BaseUrl/limited" -Headers @{
            "X-Forwarded-For" = "198.51.100.10"
        } -UseBasicParsing).StatusCode
    }
}
$changed = Get-StatusCode {
    (Invoke-WebRequest "$BaseUrl/limited" -Headers @{
        "X-Forwarded-For" = "203.0.113.20"
    } -UseBasicParsing).StatusCode
}
"first-client=$($forwarded -join ', '); changed-forwarded-client=$changed"
