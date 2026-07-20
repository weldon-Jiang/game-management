#!/usr/bin/env pwsh
# ============================================
# SIT environment start/build script.
# Usage:
#   ./start-sit.ps1
#   ./start-sit.ps1 -Services backend
#   ./start-sit.ps1 -Services backend,gateway
#   ./start-sit.ps1 -Services backend -NoBuild
#   ./start-sit.ps1 -Profile app
#   ./start-sit.ps1 -Profile core
# Legacy positional style:
#   ./start-sit.ps1 full backend
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

$EnvFiles = @('.env', '.env.sit')
$Tag = 'sit'
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

$ServiceDesc = if ($Services.Count -gt 0) { ($Services -join ', ') } else { 'all' }
$BuildDesc = if ($NoBuild) { 'no-build' } else { 'build' }

Write-Host "[$Tag] env-files=$($EnvFiles -join ', '), profile=$Profile, services=$ServiceDesc, mode=$BuildDesc starting..." -ForegroundColor $Color
& (Join-Path $PSScriptRoot 'compose-up.ps1') -EnvFiles $EnvFiles -Profile $Profile -Services $Services -NoBuild:$NoBuild
docker compose --env-file $($EnvFiles[0]) --env-file $($EnvFiles[1]) -f docker-compose.yml ps
