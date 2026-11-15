param([int]$StartPort = 8200)

$apps = @(
    @{ Name = "slowapi"; Module = "app.slowapi_app:app" },
    @{ Name = "pyrate-limiter"; Module = "app.pyrate_limiter_app:app" },
    @{ Name = "throttled-py"; Module = "app.throttled_app:app" }
)
$stores = @(
    @{ Name = "redis"; Service = "redis"; Url = "redis://localhost:6381/0" },
    @{ Name = "valkey"; Service = "valkey"; Url = "valkey://localhost:6382/0" },
    @{ Name = "dragonfly"; Service = "dragonfly"; Url = "redis://localhost:6383/0" }
)

function Status([string]$Url, [hashtable]$Headers = @{}) {
    try { return (Invoke-WebRequest $Url -Headers $Headers -UseBasicParsing -TimeoutSec 10).StatusCode }
    catch { if ($_.Exception.Response) { return [int]$_.Exception.Response.StatusCode }; return 0 }
}

function Statuses([string]$Url, [int]$Count, [hashtable]$Headers = @{}) {
    return (1..$Count | ForEach-Object { Status $Url $Headers })
}

for ($i = 0; $i -lt $apps.Count; $i++) {
    for ($j = 0; $j -lt $stores.Count; $j++) {
        $app = $apps[$i]
        $store = $stores[$j]
        $port = $StartPort + ($i * $stores.Count) + $j
        $env:REDIS_URL = $store.Url
        $env:PYRATE_ALGORITHM = "sliding-window"
        $env:PYRATE_BUCKET_KEY = "matrix-$($app.Name)-$($store.Name)-$([guid]::NewGuid())"
        $env:THROTTLED_KEY_PREFIX = "matrix-$($app.Name)-$($store.Name)-$([guid]::NewGuid())"

        $process = Start-Process -FilePath (Resolve-Path ".\.venv\Scripts\python.exe") `
            -ArgumentList "-m", "uvicorn", $app.Module, "--host", "127.0.0.1", "--port", $port `
            -WorkingDirectory (Get-Location) -PassThru -WindowStyle Hidden
        Start-Sleep -Seconds 3
        $url = "http://127.0.0.1:$port"

        $basic = Statuses "$url/limited" 6
        $parallel = 1..20 | ForEach-Object -Parallel {
            try { (Invoke-WebRequest "$using:url/limited" -UseBasicParsing -TimeoutSec 10).StatusCode }
            catch { if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { 0 } }
        } -ThrottleLimit 20
        $xffA = Statuses "$url/limited" 5 @{ "X-Forwarded-For" = "198.51.100.10" }
        $xffB = Status "$url/limited" @{ "X-Forwarded-For" = "203.0.113.20" }

        docker compose stop $store.Service | Out-Null
        Start-Sleep -Seconds 2
        $stopped = Status "$url/limited"
        docker compose start $store.Service | Out-Null
        Start-Sleep -Seconds 3

        $counts = $parallel | Group-Object | Sort-Object Name | ForEach-Object { "$($_.Name)=$($_.Count)" }
        Write-Output "$($app.Name)/$($store.Name): basic=$($basic -join ','); parallel=$($counts -join ','); xff=$($xffA -join ',')/$xffB; stopped=$stopped"
        if (Get-Process -Id $process.Id -ErrorAction SilentlyContinue) { Stop-Process -Id $process.Id -Force }
    }
}
