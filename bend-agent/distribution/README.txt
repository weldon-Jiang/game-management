# Bend Agent 商户安装包

## 目录结构

```
BendAgent/
├── BendAgent.exe          # 主程序（双击运行）
├── agent.yaml            # 配置文件
├── templates/            # 游戏截图模板（可选）
└── README.txt            # 使用说明
```

## 文件说明

### BendAgent.exe
主程序，双击即可运行。首次运行会自动创建必要的文件夹。

### agent.yaml
配置文件，包含以下选项：
```yaml
backend:
  base_url: "http://你的服务器地址:端口"
  ws_url: "ws://你的服务器地址:端口"

agent:
  heartbeat_interval: 30  # 心跳间隔（秒）

video:
  fps: 10                # 视频帧率

template:
  threshold: 0.8         # 模板匹配灵敏度 (0-1)
```

### templates/
游戏截图模板文件夹。首次运行会自动创建。

---

## 安装步骤

### 步骤 1：解压安装包
将 `BendAgent.zip` 解压到任意目录（建议：C:\BendAgent）

### 步骤 2：配置服务器地址
用记事本打开 `agent.yaml`，修改 `backend.base_url` 和 `backend.ws_url` 为你的平台服务器地址：
```yaml
backend:
  base_url: "http://你的平台域名或IP:8080"
  ws_url: "ws://你的平台域名或IP:8080"
```

### 步骤 3：运行程序
双击 `BendAgent.exe` 运行程序。

### 步骤 4：在平台绑定 Agent
1. 登录平台管理后台
2. 进入「Agent管理」页面
3. 点击「添加Agent」，获取 Agent ID 和 Secret
4. 程序运行后会自动注册到平台

---

## 常见问题

### Q: 运行时提示 "找不到 DLL"
A: 需要安装 Visual C++ Redistributable
   下载地址：https://aka.ms/vs/17/release/vc_redist.x64.exe

### Q: 程序启动后立即退出
A: 请检查 agent.yaml 中的服务器地址是否正确

### Q: 如何查看运行日志
A: 日志文件保存在程序目录下的 `logs/` 文件夹中

### Q: 如何停止程序
A: 在程序窗口按 `Ctrl+C` 或关闭窗口即可

---

## 系统要求

- 操作系统：Windows 10/11 (64位)
- 内存：至少 4GB RAM
- 磁盘：至少 500MB 可用空间
- 网络：需要连接互联网

---

## 技术支持

如遇问题，请联系客服。
