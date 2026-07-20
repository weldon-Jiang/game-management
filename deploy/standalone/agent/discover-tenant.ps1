# =================================================================
# 同局域网分控发现检测(Agent 安装前调用)
# =================================================================
# 监听 UDP 47820 约 6 秒,收到 BENDTENANT 广播则说明局域网已有分控运行,
# 退出码 0(可继续安装 Agent)。
# 未发现则退出码 1(Agent 安装中止,提示用户先装分控)。
# =================================================================
param([int]$TimeoutSec = 6)
$ErrorActionPreference = "Stop"
try {
    $udp = New-Object System.Net.Sockets.UdpClient
    $udp.Client.SetSocketOption("System.Net.Sockets.SocketOptionLevel","Socket","System.Net.Sockets.SocketOptionName","ReuseAddress", $true)
    $udp.Client.Bind([System.Net.IPEndPoint]::new([System.Net.IPAddress]::Any, 47820))
    $udp.Client.ReceiveTimeout = ($TimeoutSec * 1000)
    $ep = [System.Net.IPEndPoint]::new([System.Net.IPAddress]::Any, 0)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $bytes = $udp.Receive([ref]$ep)
            $text = [System.Text.Encoding]::UTF8.GetString($bytes)
            if ($text -like "BENDTENANT|*") {
                Write-Host "FOUND_TENANT: $text (from $($ep.Address))"
                exit 0
            }
        } catch [System.Net.Sockets.SocketException] {
            break
        }
    }
    Write-Host "NO_TENANT_FOUND"
    exit 1
} catch {
    Write-Host "discover-tenant error: $($_.Exception.Message) -> fail"
    exit 1
}
