param([switch]$InstallOCR)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $projectRoot
foreach ($program in @('uv', 'node', 'npm')) {
    if (-not (Get-Command $program -ErrorAction SilentlyContinue)) {
        throw "Install $program using its official installer, then rerun setup. See docs/DEMO.md."
    }
}
$env:UV_LINK_MODE = 'copy'
$env:UV_CACHE_DIR = Join-Path $projectRoot 'data\exports\setup-cache'
$env:TEMP = Join-Path $projectRoot 'data\exports\setup-temp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
uv sync --frozen --extra dev
if ($LASTEXITCODE -ne 0) { throw 'Locked Python installation failed.' }
Push-Location -LiteralPath (Join-Path $projectRoot 'frontend')
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw 'Locked frontend installation failed.' }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
    Write-Output 'Created private .env. Enter existing API keys there; never commit it.'
}
if ($InstallOCR) {
    winget install --id UB-Mannheim.TesseractOCR --exact --source winget --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
    if ($LASTEXITCODE -notin @(0, -1978335189)) { throw 'OCR installation failed; inspect winget output.' }
}
& '.\.venv\Scripts\python.exe' -m alembic -c backend/alembic.ini upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Database migrations failed.' }
& '.\.venv\Scripts\python.exe' scripts/doctor.py
if ($LASTEXITCODE -ne 0) { throw 'Local dependency check failed.' }
Write-Output 'Setup complete. Verify free account access with scripts/configure_free.py before starting live research.'
