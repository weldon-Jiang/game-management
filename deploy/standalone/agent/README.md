# BendAgent 安装包

Agent 是装在挂机电脑上的自动化执行端，连接**同局域网的分控平台**接收任务、控制 Xbox 云游戏自动化。**免注册码、免手填地址**，安装即用。

安装包：`BendAgentSetup.exe`（由 `deploy/standalone/build-agent-package.ps1` 产出，内嵌 BendAgent.exe + Chromium + VC++ redist）。

---

## 前置条件（重要）

**必须先在同局域网安装并启动分控平台**（`BendPlatformTenantSetup.exe`）。分控没装/没启动时，Agent 安装会中止并提示先装分控。

---

## 安装

1. 把 `BendAgentSetup.exe` 拷到 Agent 机器（Windows 10/11，与分控同局域网；也可以装在分控同一台机器）。
2. 双击运行 → 选择安装路径（默认 `C:\BendAgent`）→ 下一步。
3. **安装前自动检测**：监听 UDP 6 秒，若未发现同局域网分控 → **安装失败**，提示"未发现分控服务，请先安装分控平台服务（BendPlatformTenantSetup.exe）"。
4. 安装器自动完成：
   - 静默安装 VC++ Redistributable（`vc_redist.x64.exe /install /quiet`，已装则跳过）
   - 解压 BendAgent.exe + 场景模板
   - 解压内嵌 Playwright Chromium（离线，不运行时下载）
   - 用 `setx /M` 设系统环境变量 `PLAYWRIGHT_BROWSERS_PATH` 指向内嵌 Chromium
   - 用 nssm 注册 `BendAgent` 服务（开机自启），重定向 stdout/stderr 到 logs
   - 启动服务
5. 安装完成**弹提示**"已自动发现分控并注册、已上线"。
6. Agent 首次启动自动完成（**全程商户零操作**）：
   - 读 `agent.yaml`：若 `backend.base_url` 为占位 → UDP 监听 8 秒**自动发现分控 IP** → 回写 agent.yaml
   - 调分控 `POST /api/agents/auto-register` **免注册码自动注册** → 拿到 agentId/agentSecret
   - 连分控 WebSocket → 接收任务、上报心跳（30s）开始干活

> 安装需管理员权限（注册服务 + 设系统环境变量 + VC++ redist）。

## 工作机制（无需商户干预）

- **通信**：Agent 用 `agentId + agentSecret`（注册时自动获得），HTTP 带 `X-Agent-Id`/`X-Agent-Secret` 头，WS 长连 + 30s 心跳。不连总控。
- **发现分控**：分控每 5 秒 UDP 广播（端口 47820）自身 IP，Agent 监听获取。
- **分控 IP 变动**：Agent WS 断开重连，连续失败 3 次自动重新 UDP 发现分控新 IP，更新配置后重连，无需人工干预。
- **升级**：分控代理拉总控版本清单，Agent 收到 `version_update` 后下载（从分控下）、冷更新重启替换。

## 服务

| 服务名 | 说明 |
|---|---|
| BendAgent | Agent 主服务，开机自启（SERVICE_AUTO_START） |

管理：`services.msc` 或 `net stop/start BendAgent`。

## 运行日志

全部在**安装目录下 `logs/`**：

| 文件 | 内容 |
|---|---|
| `service_stdout.log` | nssm 重定向的服务 stdout（含启动发现分控、自动注册日志） |
| `service_stderr.log` | 服务 stderr |
| `agent.log` | Agent 主日志（JSON，任务执行、心跳、错误） |
| `stream_log/stream_{账号名}.log` | 串流账号专用日志 |
| `game_log/game_{账号名}_{日期}.log` | 游戏账号日志 |

查看：开始菜单 → BendAgent → **查看运行日志**（打开 logs 目录），或 `Get-Content -Wait logs\service_stdout.log` 实时跟踪启动过程。

## 安装目录结构

```
BendAgent\
├── BendAgent.exe          # 主程序（PyInstaller --onefile + PyArmor 混淆）
├── agent.yaml             # 配置（base_url 自动发现回写,无需手填）
├── chromium\              # 内嵌 Playwright Chromium（离线）
├── templates\             # 场景模板图片
├── credentials\           # 自动注册后的凭证（agent_credentials.json）
├── logs\                  # 运行日志
├── nssm.exe
├── view-logs.bat          # 查看日志快捷方式
└── uninstall_agent.ps1
```

## 卸载

控制面板卸载或运行安装目录卸载程序。卸载会停止 `BendAgent` 服务、通知分控、清除凭证和注册表安装标记。可选删除目录。

## 常见问题

- **安装失败提示"未发现分控"**：先在同局域网机器装并启动 `BendPlatformTenantSetup.exe`，确认分控运行（桌面快捷方式能打开后台）后再装 Agent。
- **Agent 装上但没上线**：看 `logs/service_stdout.log`，确认①发现分控成功②自动注册成功（分控 license 校验通过、`AGENT_AUTO_REGISTER_ENABLED=true`）③WS 连接成功。常见是分控还没完成 license 校验（分控刚启动需向总控校验，稍等）。
- **换机器/重装**：Agent 的 agentId 基于机器指纹，换机器会生成新 agentId 重新注册（旧记录在分控后台可清理）。同机器重装会复用 agentId。
- **Playwright 报找不到浏览器**：确认 `PLAYWRIGHT_BROWSERS_PATH` 系统环境变量指向 `安装目录\chromium`（安装时已设，需重启服务/重开终端生效）。
- **VC++ 安装失败**：手动装 `vc_redist.x64.exe`（在安装目录或微软官网下载）后重试。

## 与分控同机安装

分控和 Agent 可装同一台机器：服务名不冲突（分控 `BendTenant*`、Agent `BendAgent`），端口不冲突（分控 8090/8060/8061/3306，Agent 不监听入站）。Agent 自动发现的分控 IP 即本机，连 `127.0.0.1:8060`。

## 前置打包资源（打包者看）

`deploy/standalone/staging/agent/` 下需备好：`chromium/`(Playwright Chromium 目录) · `vc_redist.x64.exe` · `nssm.exe`。BendAgent.exe 由 `bend-agent/scripts/build.bat` 产出（PyInstaller+PyArmor）。详见 [AGENTS.md 生产打包规则](../../AGENTS.md)。
