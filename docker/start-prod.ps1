#!/usr/bin/env pwsh
# ============================================
# Production environment start/build script.
# Usage:
#   ./start-prod.ps1
#   ./start-prod.ps1 -Services backend
#   ./start-prod.ps1 -Services backend,gateway
#   ./start-prod.ps1 -Services backend -NoBuild
#   ./start-prod.ps1 -Profile app
#   ./start-prod.ps1 -Profile core
# Legacy positional style:
#   ./start-prod.ps1 full backend
# Before production deployment, replace every CHANGE_ME placeholder.
# ============================================
param(
    [string]$Profile = 'full',
    [string[]]$Services = @(),
    [switch]$NoBuild,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Positional = @()
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

$EnvFile = '.env.prod'
$Tag = 'prod'
$Color = 'Yellow'

# Block production deployment when CHANGE_ME placeholders remain.
$envPath = Join-Path $PSScriptRoot $EnvFile
if (-not (Test-Path $envPath)) {
    Write-Host "[prod] $EnvFile not found. Create it with real secrets first." -ForegroundColor Red
    exit 1
}
$placeholders = Select-String -Path $envPath -Pattern 'CHANGE_ME' -SimpleMatch
if ($placeholders) {
    Write-Host "[prod] $EnvFile still contains CHANGE_ME placeholders:" -ForegroundColor Red
    $placeholders | ForEach-Object { Write-Host ("  L{0}: {1}" -f $_.LineNumber, $_.Line.Trim()) -ForegroundColor Red }
    Write-Host "[prod] Replace placeholders before production deployment." -ForegroundColor Red
    exit 1
}
$answer = Read-Host "[prod] Production deployment. Confirm .env.prod has real secrets. Type yes to continue"
if ($answer -ne 'yes') {
    Write-Host "[prod] Deployment cancelled." -ForegroundColor Yellow
    exit 0
}

# Legacy positional style: start-xxx.ps1 <profile> [service...]
if ($Positional.Count -ge 1 -and -not $PSBoundParameters.ContainsKey('Profile')) {
    $Profile = $Positional[0]
    if ($Positional.Count -ge 2 -and $Services.Count -eq 0) {
        $Services = $Positional[1..($Positional.Count - 1)]
    }
}

# Service-specific starts use full profile so dependencies resolve.
if ($Services.Count -gt 0 -and -not $PSBoundParameters.ContainsKey('Profile')) {
    $Profile = 'full'
}

$BuildFlag = if ($NoBuild) { @() } else { @('--build') }
$ServiceDesc = if ($Services.Count -gt 0) { ($Services -join ', ') } else { 'all' }
$BuildDesc = if ($NoBuild) { 'no-build' } else { 'build' }

Write-Host "[$Tag] env-file=$EnvFile, profile=$Profile, services=$ServiceDesc, mode=$BuildDesc starting..." -ForegroundColor $Color
docker compose --env-file $EnvFile -f docker-compose.yml --profile $Profile up -d @BuildFlag @Services
docker compose --env-file $EnvFile -f docker-compose.yml ps
