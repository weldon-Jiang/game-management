#!/usr/bin/env pwsh
# ============================================
# Dev hot-deploy: local build + docker cp + restart (no docker build / registry pull)
#
# Usage:
#   ./hot-deploy-dev.ps1
#   ./hot-deploy-dev.ps1 -Services backend
#   ./hot-deploy-dev.ps1 -Services backend,gateway
#   ./hot-deploy-dev.ps1 -SkipBuild
# ============================================
param(
    [string[]]$Services = @(),
    [switch]$SkipBuild,
    [int]$HealthWaitSeconds = 45
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

$EnvFile = '.env'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Tag = 'hot-deploy'
$Color = 'Cyan'

function Normalize-ServiceList {
    param([string[]]$InputServices)
    if (-not $InputServices -or $InputServices.Count -eq 0) {
        return @('backend', 'gateway', 'frontend')
    }
    $normalized = @()
    foreach ($item in $InputServices) {
        if ([string]::IsNullOrWhiteSpace($item)) { continue }
        foreach ($part in ($item -split ',')) {
            $name = $part.Trim().ToLowerInvariant()
            if ($name -eq 'all') {
                return @('backend', 'gateway', 'frontend')
            }
            if ($name) { $normalized += $name }
        }
    }
    if ($normalized.Count -eq 0) {
        return @('backend', 'gateway', 'frontend')
    }
    return $normalized | Select-Object -Unique
}

function Assert-ContainerRunning {
    param([string]$Name)
    $running = docker ps --filter "name=$Name" --filter "status=running" --format "{{.Names}}" 2>$null
    if ($running -ne $Name) {
        Write-Host "[$Tag] container $Name is not running. Run: ./start-dev.ps1 -NoBuild" -ForegroundColor Red
        exit 1
    }
}

function Test-ContainerHealthy {
    param([string]$Name)
    $status = docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' $Name 2>$null
    return ($status -eq 'healthy' -or $status -eq 'none')
}

function Wait-ComposeHealthy {
    param(
        [int]$Seconds,
        [string[]]$ContainerNames
    )
    Write-Host "[$Tag] waiting for health checks (max ${Seconds}s)..." -ForegroundColor $Color
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        Start-Sleep -Seconds 3
        $allOk = $true
        foreach ($name in $ContainerNames) {
            if (-not (Test-ContainerHealthy -Name $name)) {
                $allOk = $false
                break
            }
        }
        if ($allOk) { return $true }
    } while ((Get-Date) -lt $deadline)
    return $false
}

$targets = Normalize-ServiceList -InputServices $Services
Write-Host "[$Tag] services=$($targets -join ', '), skipBuild=$SkipBuild" -ForegroundColor $Color

foreach ($svc in $targets) {
    switch ($svc) {
        'backend' { Assert-ContainerRunning 'bend-xbox-backend' }
        'gateway' { Assert-ContainerRunning 'bend-xbox-gateway' }
        'frontend' { Assert-ContainerRunning 'bend-xbox-frontend' }
        default {
            Write-Host "[$Tag] unknown service: $svc (backend|gateway|frontend)" -ForegroundColor Red
            exit 1
        }
    }
}

if (-not $SkipBuild) {
    if ($targets -contains 'backend') {
        Write-Host "[$Tag] mvn package (bend-platform)..." -ForegroundColor $Color
        Push-Location (Join-Path $RepoRoot 'bend-platform')
        mvn -q package -DskipTests
        if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
        Pop-Location
    }
    if ($targets -contains 'gateway') {
        Write-Host "[$Tag] mvn package (bend-gateway)..." -ForegroundColor $Color
        Push-Location (Join-Path $RepoRoot 'bend-gateway')
        mvn -q package -DskipTests
        if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
        Pop-Location
    }
    if ($targets -contains 'frontend') {
        Write-Host "[$Tag] npm run build (bend-platform-web)..." -ForegroundColor $Color
        Push-Location (Join-Path $RepoRoot 'bend-platform-web')
        npm run build
        if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
        Pop-Location
    }
}

$restart = @()
if ($targets -contains 'backend') {
    $jar = Join-Path $RepoRoot 'bend-platform\target\bend-platform-1.0.0.jar'
    if (-not (Test-Path $jar)) {
        Write-Host "[$Tag] missing $jar - build first or drop -SkipBuild" -ForegroundColor Red
        exit 1
    }
    Write-Host "[$Tag] deploying backend jar..." -ForegroundColor $Color
    docker cp $jar bend-xbox-backend:/app/app.jar
    $restart += 'bend-xbox-backend'
}
if ($targets -contains 'gateway') {
    $jar = Join-Path $RepoRoot 'bend-gateway\target\bend-gateway-1.0.0.jar'
    if (-not (Test-Path $jar)) {
        Write-Host "[$Tag] missing $jar - build first or drop -SkipBuild" -ForegroundColor Red
        exit 1
    }
    Write-Host "[$Tag] deploying gateway jar..." -ForegroundColor $Color
    docker cp $jar bend-xbox-gateway:/app/app.jar
    $restart += 'bend-xbox-gateway'
}
if ($targets -contains 'frontend') {
    $dist = Join-Path $RepoRoot 'bend-platform-web\dist'
    if (-not (Test-Path (Join-Path $dist 'index.html'))) {
        Write-Host "[$Tag] missing $dist\index.html - build first or drop -SkipBuild" -ForegroundColor Red
        exit 1
    }
    Write-Host "[$Tag] deploying frontend dist..." -ForegroundColor $Color
    docker cp "$dist\." bend-xbox-frontend:/usr/share/nginx/html/
    $restart += 'bend-xbox-frontend'
}

if ($restart.Count -gt 0) {
    Write-Host "[$Tag] restarting: $($restart -join ', ')" -ForegroundColor $Color
    docker restart @restart
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if (-not (Wait-ComposeHealthy -Seconds $HealthWaitSeconds -ContainerNames $restart)) {
    Write-Host "[$Tag] health check timed out. Run: docker compose --env-file $EnvFile -f docker-compose.yml ps" -ForegroundColor Yellow
    exit 1
}

try {
    $health = Invoke-RestMethod -Uri 'http://localhost:8060/actuator/health' -TimeoutSec 15
    Write-Host "[$Tag] gateway health: $($health.status)" -ForegroundColor Green
} catch {
    Write-Host "[$Tag] gateway health request failed: $($_.Exception.Message)" -ForegroundColor Yellow
}

docker compose --env-file $EnvFile -f docker-compose.yml ps
Write-Host "[$Tag] done" -ForegroundColor Green
