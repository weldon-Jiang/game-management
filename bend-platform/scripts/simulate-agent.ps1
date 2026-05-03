# Agent Simulator - Test Agent and Management Platform Interaction
# Usage: .\simulate-agent.ps1 -BaseUrl "http://localhost:8090"

param(
    [string]$BaseUrl = "http://localhost:8090",
    [string]$MerchantId = "",
    [int]$AgentCount = 3,
    [int]$HeartbeatInterval = 30
)

function Generate-RandomId {
    param([int]$Length = 32)
    $chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    $result = ""
    for ($i = 0; $i -lt $Length; $i++) {
        $result += $chars[(Get-Random -Maximum $chars.Length)]
    }
    return $result
}

function Generate-AgentId {
    return "agent-$(Generate-RandomId -Length 8)"
}

function Generate-AgentSecret {
    return "sec_$(Generate-RandomId -Length 48)"
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Step 1: Admin Login" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "Username: " -NoNewline -ForegroundColor Yellow
$username = Read-Host
Write-Host "Password: " -NoNewline -ForegroundColor Yellow
$password = Read-Host -AsSecureString
$password = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($password))

$loginResponse = Invoke-RestMethod -Uri "$BaseUrl/api/auth/login" -Method POST -ContentType "application/json" -Body (@{ loginKey = $username; password = $password } | ConvertTo-Json)

if ($loginResponse.code -ne 200 -and $loginResponse.code -ne 0) {
    Write-Host "Login failed: $($loginResponse.message)" -ForegroundColor Red
    exit 1
}

$token = $loginResponse.data.token
$role = $loginResponse.data.role
$userMerchantId = $loginResponse.data.merchantId
Write-Host "Login successful! Role: $role" -ForegroundColor Green

$isPlatformAdmin = ($role -eq "platform_admin")
Write-Host "Platform Admin: $isPlatformAdmin" -ForegroundColor Gray

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Step 2: Generate Registration Codes" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$MerchantId = $userMerchantId

if ($isPlatformAdmin) {
    # 平台管理员：获取所有商户列表
    $merchantsResponse = Invoke-RestMethod -Uri "$BaseUrl/api/merchants/all" -Method GET -Headers @{ Authorization = "Bearer $token" }

    if ($merchantsResponse.code -ne 200) {
        Write-Host "Failed to get merchants: $($merchantsResponse.message)" -ForegroundColor Red
        exit 1
    }

    $merchants = $merchantsResponse.data
    Write-Host "Available merchants:" -ForegroundColor Yellow
    for ($j = 0; $j -lt $merchants.Count; $j++) {
        Write-Host "  [$($j+1)] $($merchants[$j].name) (ID: $($merchants[$j].id))" -ForegroundColor White
    }

    if (-not $script:MerchantId) {
        Write-Host "`nSelect merchant number: " -NoNewline -ForegroundColor Yellow
        $choice = Read-Host
        $MerchantId = $merchants[$choice - 1].id
    }

    Write-Host "Using merchant: $MerchantId" -ForegroundColor Green
} else {
    # 商户用户：使用自己的商户
    Write-Host "Merchant user detected. Using your merchant: $userMerchantId" -ForegroundColor Green
}
Write-Host "Generating $AgentCount registration codes..." -ForegroundColor Green

$generateResponse = Invoke-RestMethod -Uri "$BaseUrl/api/registration-codes/generate" -Method POST -ContentType "application/json" -Headers @{ Authorization = "Bearer $token" } -Body (@{ merchantId = $MerchantId; count = $AgentCount } | ConvertTo-Json)

if ($generateResponse.code -ne 200) {
    Write-Host "Failed to generate codes: $($generateResponse.message)" -ForegroundColor Red
    exit 1
}

$registrationCodes = $generateResponse.data
Write-Host "Generated $($registrationCodes.Count) codes:" -ForegroundColor Green
$registrationCodes | ForEach-Object { Write-Host "  - $_" -ForegroundColor White }

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Step 3: Simulate Agent Registration" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$agents = @()
$codeIndex = 0
$script:startTime = Get-Date

for ($i = 1; $i -le $AgentCount; $i++) {
    $agentId = Generate-AgentId
    $agentSecret = Generate-AgentSecret
    $registrationCode = $registrationCodes[$codeIndex++]

    Write-Host "`nRegistering Agent-$i..." -ForegroundColor Yellow
    Write-Host "  AgentID: $agentId" -ForegroundColor White
    Write-Host "  AgentSecret: $($agentSecret.Substring(0, 20))..." -ForegroundColor White
    Write-Host "  Code: $registrationCode" -ForegroundColor White

    $hostIp = "192.168.1.$(Get-Random -Minimum 10 -Maximum 250)"

    try {
        $registerResponse = Invoke-RestMethod -Uri "$BaseUrl/api/agents/register" -Method POST -Headers @{ "X-Agent-ID" = $agentId; "X-Agent-Secret" = $agentSecret } -ContentType "application/x-www-form-urlencoded" -Body @{ registrationCode = $registrationCode; host = $hostIp; port = 8888; version = "1.0.0" }

        if ($registerResponse.code -eq 200) {
            Write-Host "  Success! InstanceID: $($registerResponse.data.id)" -ForegroundColor Green
            $agents += @{ Index = $i; AgentId = $agentId; AgentSecret = $agentSecret; Host = $hostIp; InstanceId = $registerResponse.data.id; Status = "online" }
        } else {
            Write-Host "  Failed: $($registerResponse.message)" -ForegroundColor Red
        }
    } catch {
        Write-Host "  Exception: $($_.Exception.Message)" -ForegroundColor Red
    }
}

if ($agents.Count -eq 0) {
    Write-Host "`nNo agents registered successfully. Exiting." -ForegroundColor Red
    exit 1
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Step 4: Heartbeat Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Sending heartbeat every $HeartbeatInterval seconds" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop`n" -ForegroundColor Gray

$heartbeatCount = 0

try {
    while ($true) {
        Start-Sleep -Seconds $HeartbeatInterval
        $heartbeatCount++

        Write-Host "`n--- Heartbeat #$heartbeatCount ---" -ForegroundColor Cyan

        foreach ($agent in $agents) {
            try {
                $elapsed = "{0:N1}" -f ((Get-Date) - $script:startTime).TotalMinutes
                $response = Invoke-RestMethod -Uri "$BaseUrl/api/agents/heartbeat" -Method POST -Headers @{ "X-Agent-ID" = $agent.AgentId; "X-Agent-Secret" = $agent.AgentSecret } -ContentType "application/x-www-form-urlencoded" -Body @{ status = "online"; version = "1.0.0" } -TimeoutSec 5

                if ($response.code -eq 200) {
                    Write-Host "  Agent-$($agent.Index): ${elapsed} minutes online" -ForegroundColor Green
                } else {
                    Write-Host "  Agent-$($agent.Index): Failed" -ForegroundColor Red
                }
            } catch {
                Write-Host "  Agent-$($agent.Index): Exception" -ForegroundColor Red
            }
        }

        Write-Host "  Next heartbeat in $HeartbeatInterval seconds (Ctrl+C to stop)" -ForegroundColor Gray
    }
} finally {
    Write-Host "`nHeartbeat loop stopped" -ForegroundColor Yellow
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Options" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "[1] Uninstall all Agents" -ForegroundColor Yellow
Write-Host "[2] Offline all Agents" -ForegroundColor Yellow
Write-Host "[3] View Agent list" -ForegroundColor Yellow
Write-Host "[Q] Exit" -ForegroundColor Yellow

$choice = Read-Host "Select"

switch ($choice) {
    "1" {
        Write-Host "`nUninstalling..." -ForegroundColor Yellow
        foreach ($agent in $agents) {
            try {
                $response = Invoke-RestMethod -Uri "$BaseUrl/api/agents/uninstall" -Method POST -Headers @{ "X-Agent-ID" = $agent.AgentId; "X-Agent-Secret" = $agent.AgentSecret } -ContentType "application/x-www-form-urlencoded" -Body @{ reason = "Test uninstall"; clearRegistry = $false } -TimeoutSec 5
                Write-Host "  Agent-$($agent.Index): $($response.message)" -ForegroundColor Green
            } catch {
                Write-Host "  Agent-$($agent.Index): Failed" -ForegroundColor Red
            }
        }
    }
    "2" {
        Write-Host "`nOfflining..." -ForegroundColor Yellow
        foreach ($agent in $agents) {
            try {
                $response = Invoke-RestMethod -Uri "$BaseUrl/api/agents/offline" -Method POST -Headers @{ "X-Agent-ID" = $agent.AgentId; "X-Agent-Secret" = $agent.AgentSecret } -TimeoutSec 5
                Write-Host "  Agent-$($agent.Index): $($response.message)" -ForegroundColor Green
            } catch {
                Write-Host "  Agent-$($agent.Index): Failed" -ForegroundColor Red
            }
        }
    }
    "3" {
        Write-Host "`nCurrent Agent list:" -ForegroundColor Yellow
        $agentsResponse = Invoke-RestMethod -Uri "$BaseUrl/api/agent-instances" -Method GET -Headers @{ Authorization = "Bearer $token" } -TimeoutSec 5
        $agentsResponse.data | Format-Table -AutoSize
    }
}

Write-Host "`nScript finished" -ForegroundColor Cyan
