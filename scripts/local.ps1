param([ValidateSet('start', 'stop', 'restart', 'status')][string]$Action = 'start')
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtimeDir = Join-Path $projectRoot 'data\exports\local-runtime'
$manifestPath = Join-Path $runtimeDir 'services.json'

function Test-OwnedService($record) {
    if ($null -eq $record) { return $false }
    $processInfo = Get-Process -Id $record.pid -ErrorAction SilentlyContinue
    if ($null -eq $processInfo) { return $false }
    $expectedTicks = if ($null -ne $record.started_ticks) { [long]$record.started_ticks } else { ([DateTimeOffset]$record.started_at).UtcTicks }
    return $processInfo.StartTime.ToUniversalTime().Ticks -eq $expectedTicks
}

function Stop-OwnedService($record) {
    if ($null -eq $record) { return }
    $processInfo = Get-Process -Id $record.pid -ErrorAction SilentlyContinue
    if ($null -eq $processInfo) { return }
    $expectedTicks = if ($null -ne $record.started_ticks) { [long]$record.started_ticks } else { ([DateTimeOffset]$record.started_at).UtcTicks }
    if ($processInfo.StartTime.ToUniversalTime().Ticks -ne $expectedTicks) {
        throw 'A recorded process ID has been reused; refusing to stop another process.'
    }
    $allProcesses = Get-CimInstance Win32_Process
    $ownedIds = [System.Collections.Generic.List[int]]::new()
    $ownedIds.Add([int]$record.pid)
    for ($index = 0; $index -lt $ownedIds.Count; $index++) {
        foreach ($child in ($allProcesses | Where-Object { $_.ParentProcessId -eq $ownedIds[$index] })) {
            if (-not $ownedIds.Contains([int]$child.ProcessId)) { $ownedIds.Add([int]$child.ProcessId) }
        }
    }
    # Stop only the recorded service and its descendants, preserving the database and exports.
    for ($index = $ownedIds.Count - 1; $index -ge 0; $index--) {
        Stop-Process -Id $ownedIds[$index] -Force -ErrorAction SilentlyContinue
    }
}

if ($Action -in @('stop', 'restart') -and (Test-Path -LiteralPath $manifestPath)) {
    $services = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($services.project_root -ne $projectRoot) { throw 'Service manifest belongs to another checkout.' }
    foreach ($serviceName in @('api', 'worker', 'frontend')) { Stop-OwnedService $services.$serviceName }
    Remove-Item -LiteralPath $manifestPath
}
if ($Action -eq 'stop') { Write-Output 'Beyond services stopped.'; exit 0 }
if ($Action -eq 'status') {
    if (-not (Test-Path -LiteralPath $manifestPath)) { Write-Output 'Beyond has no managed local services.'; exit 1 }
    $services = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($services.project_root -ne $projectRoot) { throw 'Service manifest belongs to another checkout.' }
    $allRunning = $true
    foreach ($serviceName in @('api', 'worker', 'frontend')) {
        $running = Test-OwnedService $services.$serviceName
        if (-not $running) { $allRunning = $false }
        Write-Output "$serviceName running: $running"
    }
    if ($allRunning) { exit 0 } else { exit 1 }
}
if (Test-Path -LiteralPath $manifestPath) {
    $services = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($services.project_root -ne $projectRoot) { throw 'Service manifest belongs to another checkout.' }
    foreach ($serviceName in @('api', 'worker', 'frontend')) {
        if (Test-OwnedService $services.$serviceName) {
            throw 'Managed services are still running. Use restart or status.'
        }
    }
    # All recorded services have exited. Clearing only this stale manifest does
    # not stop a process, including any unrelated process that reused an ID.
    Remove-Item -LiteralPath $manifestPath
    Write-Output 'Recovered stale local service records.'
}
foreach ($servicePort in @(8000, 5173)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $servicePort -ErrorAction SilentlyContinue) {
        throw "Port $servicePort is already in use. Stop its existing service before starting Beyond."
    }
}
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$vitePath = Join-Path $projectRoot 'frontend\node_modules\vite\bin\vite.js'
if (-not (Test-Path -LiteralPath $pythonPath) -or -not (Test-Path -LiteralPath $vitePath)) {
    throw 'Install the Python and frontend dependencies first; see README.md.'
}
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
$localTesseract = Join-Path $runtimeDir 'tesseract'
if (Test-Path -LiteralPath (Join-Path $localTesseract 'tesseract.exe')) {
    $env:PATH = "$localTesseract;$env:PATH"
}
$nodePath = (Get-Command node -ErrorAction Stop).Source
& $pythonPath -m alembic -c (Join-Path $projectRoot 'backend\alembic.ini') upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Database migrations failed.' }
$services = [ordered]@{ project_root = $projectRoot }
$serviceDefinitions = @(
    @{ Name = 'api'; Executable = $pythonPath; Directory = $projectRoot; Arguments = @('-m', 'uvicorn', 'signal_research.main:app', '--host', '127.0.0.1', '--port', '8000') },
    @{ Name = 'worker'; Executable = $pythonPath; Directory = $projectRoot; Arguments = @('-m', 'signal_research.worker.main') },
    @{ Name = 'frontend'; Executable = $nodePath; Directory = (Join-Path $projectRoot 'frontend'); Arguments = @('node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5173', '--strictPort') }
)
try {
    foreach ($definition in $serviceDefinitions) {
        $processInfo = Start-Process -FilePath $definition.Executable -ArgumentList $definition.Arguments -WorkingDirectory $definition.Directory -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeDir "$($definition.Name).stdout.log") -RedirectStandardError (Join-Path $runtimeDir "$($definition.Name).stderr.log") -PassThru
        $services[$definition.Name] = @{ pid = $processInfo.Id; started_ticks = $processInfo.StartTime.ToUniversalTime().Ticks }
        $services | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath
    }
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/health/ready' -TimeoutSec 1 | Out-Null
            Invoke-WebRequest 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 1 | Out-Null
            Write-Output 'Beyond is ready at http://127.0.0.1:5173/ (API: http://127.0.0.1:8000/docs).'
            exit 0
        } catch { Start-Sleep -Milliseconds 500 }
    }
    throw 'Local services did not become ready. Inspect data/exports/local-runtime/*.log.'
} catch {
    foreach ($serviceName in @('api', 'worker', 'frontend')) { Stop-OwnedService $services[$serviceName] }
    if (Test-Path -LiteralPath $manifestPath) { Remove-Item -LiteralPath $manifestPath }
    throw
}
