#!/usr/bin/env pwsh
# ============================================
# Dev environment start/build script.
# Usage:
#   ./start-dev.ps1
#   ./start-dev.ps1 -Services backend
#   ./start-dev.ps1 -Services backend,gateway
#   ./start-dev.ps1 -Services backend -NoBuild
#   ./start-dev.ps1 -Profile app
#   ./start-dev.ps1 -Profile core
# Legacy positional style:
#   ./start-dev.ps1 full backend
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

$EnvFile = '.env.dev'
$Tag = 'dev'
$Color = 'Cyan'

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
