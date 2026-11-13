param([switch]$Mobile)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Install and start Docker Desktop with Linux containers first.' }
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
docker info --format '{{.ServerVersion}}' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Docker engine is unavailable. Start Docker Desktop and wait until its engine is ready.' }
docker compose up --build -d
if ($LASTEXITCODE -ne 0) { throw 'Startup failed. Run docker compose logs to inspect the failed service.' }
Write-Host 'CHINNU is starting at http://localhost:8080 (or the APP_PORT set in .env).'
Write-Host 'Use docker compose ps to check readiness.'
if ($Mobile) {
    & "$PSScriptRoot\start-mobile.ps1"
}