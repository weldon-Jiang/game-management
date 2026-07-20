#!/usr/bin/env pwsh
# ============================================
# 共享：docker compose up 参数组装（避免 @BuildFlag 展开导致 "no such service: -"）
# ============================================
param(
    [Parameter(Mandatory = $true)]
    [string[]]$EnvFiles,
    [Parameter(Mandatory = $true)]
    [string]$Profile,
    [string[]]$Services = @(),
    [switch]$NoBuild
)

$ErrorActionPreference = 'Stop'

function Normalize-ServiceList {
    param([string[]]$InputServices)
    $normalized = @()
    foreach ($item in $InputServices) {
        if ([string]::IsNullOrWhiteSpace($item)) { continue }
        foreach ($part in ($item -split ',')) {
            $name = $part.Trim()
            if ($name) { $normalized += $name }
        }
    }
    return $normalized
}

$serviceList = Normalize-ServiceList -InputServices $Services

$composeArgs = @('compose')
foreach ($ef in $EnvFiles) {
    $composeArgs += '--env-file', $ef
}
$composeArgs += @(
    '-f', 'docker-compose.yml',
    '--profile', $Profile,
    'up', '-d'
)
if (-not $NoBuild) {
    $composeArgs += '--build'
}
if ($serviceList.Count -gt 0) {
    $composeArgs += $serviceList
}

& docker @composeArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
