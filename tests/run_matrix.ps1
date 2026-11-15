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

Write-Host "Sequential limit test"
$sequential = 1..6 | ForEach-Object {
    Get-StatusCode { (Invoke-WebRequest "$BaseUrl/limited" -UseBasicParsing).StatusCode }
}
$sequential -join ", "

Write-Host "Parallel limit test"
$parallel = 1..$ParallelRequests | ForEach-Object -Parallel {
    try {
        (Invoke-WebRequest "$using:BaseUrl/limited" -UseBasicParsing -TimeoutSec 10).StatusCode
    } catch {
        if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { 0 }
    }
} -ThrottleLimit $ParallelRequests
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
