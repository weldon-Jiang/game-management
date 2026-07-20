# =================================================================
# 同局域网分控存在性检测(安装时调用)
# =================================================================
# 监听 UDP 47820 约 6 秒,若收到 BENDTENANT 开头广播,说明该局域网已有分控运行,
# 返回退出码 1(安装器据此阻止安装)。
# 退出码 0 = 未发现,可继续安装。
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
                Write-Host "DETECTED: $text (from $($ep.Address))"
                exit 1
            }
        } catch [System.Net.Sockets.SocketException] {
            # 超时,继续
            break
        }
    }
    exit 0
} catch {
    # 绑定失败或异常,不阻塞安装(降级放行)
    Write-Host "detect-tenant: $($_.Exception.Message) -> pass"
    exit 0
}
