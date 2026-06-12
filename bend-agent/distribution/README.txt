# Bend Agent 商户安装包

## 目录结构

```
BendAgent/
├── BendAgent.exe          # 主程序（双击运行）
├── agent.yaml             # 配置文件
├── uninstall_agent.ps1    # 卸载脚本（推荐）
├── templates/             # 游戏截图模板
├── logs/                  # 运行日志（自动创建）
├── credentials/           # 激活凭证（首次激活后自动创建）
└── README.txt             # 本说明文件
```

## 重要说明：每台电脑只能安装一个 Agent

- 同一台 Windows 电脑**只允许安装一份** Agent（无论解压到哪个目录）。
- 若本机已安装，再次运行其他目录下的 Agent 会提示拒绝启动。
- **同目录升级**：直接覆盖 `BendAgent.exe` 即可，无需卸载。
- **换目录重装**：必须先完成卸载（见下方「卸载步骤」），再解压到新目录。

---

## 安装步骤

### 步骤 1：解压安装包

将 `BendAgent.zip` 解压到任意目录（建议：`C:\BendAgent`）。

> 不要在一台电脑上解压到两个不同目录同时运行。

### 步骤 2：配置服务器地址

用记事本打开 `agent.yaml`，修改 `backend.base_url` 和 `backend.ws_url` 为你的平台服务器地址：

```yaml
backend:
  base_url: "http://你的平台域名或IP:8060"
  ws_url: "ws://你的平台域名或IP:8060/ws/agent"
```

### 步骤 3：运行程序

双击 `BendAgent.exe` 运行程序。

### 步骤 4：首次激活

首次运行会提示输入**商户注册码**（格式示例：`AGENT-XXXX-XXXX-XXXX`）。

1. 登录平台管理后台，在「注册码 / Agent」相关页面生成注册码
2. 在程序窗口输入注册码完成激活
3. 激活成功后，Agent 会自动连接平台并保持在线

激活凭证保存在 `credentials/agent_credentials.json`，请勿泄露。

---

## 卸载步骤

卸载会：通知平台、删除本地凭证、清除本机安装注册表标记。完成后可在本机重新安装。

### 方式一：卸载脚本（推荐）

1. 关闭正在运行的 `BendAgent.exe`（如有）
2. 右键 `uninstall_agent.ps1` → **使用 PowerShell 运行**
3. 按提示操作；若询问是否删除安装目录，确认后手动删除文件夹

> 若提示无法运行脚本，以管理员打开 PowerShell，执行：
> `Set-ExecutionPolicy -Scope Process Bypass`
> 然后：`.\uninstall_agent.ps1`

### 方式二：命令行卸载

在本安装目录打开命令提示符或 PowerShell：

```
BendAgent.exe --uninstall
```

看到「卸载完成」即表示本机可重新安装。

### 换目录重装流程

1. 在**旧安装目录**执行上述卸载步骤
2. 删除旧目录（可选）
3. 将安装包解压到**新目录**
4. 修改 `agent.yaml` 后重新运行并激活

---

## 常见问题

### Q: 提示「本机已安装 Bend Agent，每台电脑只能安装一个实例」

A: 本机已有 Agent 安装记录。请在**原安装目录**执行卸载（见上方「卸载步骤」），或运行：

```
BendAgent.exe --uninstall
```

若原目录已删除但仍报此错，在新目录运行 `uninstall_agent.ps1` 清理残留注册表。

### Q: 运行时提示「找不到 DLL」

A: 需要安装 Visual C++ Redistributable
   下载地址：https://aka.ms/vs/17/release/vc_redist.x64.exe

### Q: 程序启动后立即退出

A: 请检查 `agent.yaml` 中的服务器地址是否正确，并查看 `logs/agent.log`。

### Q: 如何查看运行日志

A: 日志文件保存在程序目录下的 `logs/` 文件夹中。

### Q: 如何停止程序

A: 在程序窗口按 `Ctrl+C` 或关闭窗口即可。停止程序**不等于**卸载。

---

## 系统要求

- 操作系统：Windows 10/11 (64位)
- 内存：至少 4GB RAM
- 磁盘：至少 500MB 可用空间
- 网络：需要能访问平台 Gateway（默认端口 8060）

---

## 技术支持

如遇问题，请联系客服。
