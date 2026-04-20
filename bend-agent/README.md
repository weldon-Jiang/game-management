# Bend Agent

Xbox 自动化控制程序 - 运行在客户端的自动化 Agent

## 功能特性

- **视频帧捕获** - 从 Xbox 串流窗口实时捕获画面
- **模板匹配** - 基于图像识别的自动化控制
- **场景检测** - 自动识别 Xbox UI 状态
- **输入控制** - 鼠标、键盘、手柄自动化
- **账号管理** - 游戏账号切换和时长管理
- **后端通信** - HTTP API 和 WebSocket 实时通信

## 项目结构

```
bend-agent/
├── configs/
│   └── agent.yaml          # Agent 配置文件
├── distribution/            # 商户分发包（打包后）
│   ├── README.txt         # 商户使用说明
│   └── agent.yaml.example  # 配置文件示例
├── docs/
│   └── BUILD_GUIDE.md     # 开发者打包指南
├── logs/                    # 日志目录
├── scripts/
│   └── build.bat           # 打包脚本
├── templates/               # 模板图像目录
├── src/
│   ├── agent/
│   │   ├── api/            # 后端通信
│   │   │   ├── client.py   # HTTP API 客户端
│   │   │   └── websocket.py # WebSocket 客户端
│   │   ├── core/           # 核心组件
│   │   │   ├── config.py   # 配置管理
│   │   │   ├── logger.py   # 日志管理
│   │   │   └── central_manager.py # 中央管理器
│   │   ├── game/           # 游戏账号管理
│   │   ├── input/          # 输入控制
│   │   ├── scene/           # 场景检测
│   │   ├── vision/          # 视觉处理
│   │   │   ├── frame_capture.py   # 帧捕获
│   │   │   └── template_matcher.py # 模板匹配
│   │   └── windows/         # 窗口管理
│   └── main.py             # 入口文件
├── requirements.txt
└── start.sh
```

---

## 开发者打包流程

### 打包前准备

安装打包工具：
```bash
pip install pyarmor pyinstaller
```

### 打包步骤

双击运行 `scripts\build.bat`，或手动执行：

```bash
# 1. 加密代码
pyarmor gen --output dist/agent --assert all --assert call src/

# 2. 复制配置和模板
copy /Y configs\* dist\agent\
xcopy /S /Q templates\* dist\agent\templates\

# 3. 打包成 exe
pyinstaller --name BendAgent ^
    --add-data "dist\agent;agent" ^
    --add-data "configs;configs" ^
    --add-data "templates;templates" ^
    --hidden-import=aiohttp ^
    --hidden-import=websockets ^
    --hidden-import=cv2 ^
    --hidden-import=numpy ^
    --hidden-import=PIL ^
    --hidden-import=pyautogui ^
    --hidden-import=win32gui ^
    --hidden-import=win32ui ^
    --hidden-import=win32con ^
    --hidden-import=yaml ^
    --onefile ^
    --console ^
    dist\agent\main.py
```

### 打包完成

`dist\release\` 目录即为可分发安装包，包含：
- `BendAgent.exe` - 主程序
- `agent.yaml` - 配置文件
- `templates/` - 模板目录
- `README.txt` - 使用说明

---

## 商户分发

### 商户安装包内容

```
BendAgent/
├── BendAgent.exe      # 主程序
├── agent.yaml        # 配置文件
├── templates/        # 模板目录
└── README.txt       # 使用说明
```

### 商户安装步骤

1. 解压安装包到任意目录
2. 修改 `agent.yaml` 中的服务器地址
3. 双击运行 `BendAgent.exe`
4. 在平台管理后台添加 Agent 并绑定

### 商户配置说明

编辑 `agent.yaml`：
```yaml
backend:
  base_url: "http://你的平台域名:8080"
  ws_url: "ws://你的平台域名:8080"
```

---

## 开发

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行

```bash
python src/main.py --agent-id <AGENT_ID> --agent-secret <AGENT_SECRET>
```

### 代码检查

```bash
ruff check src/
```

---

## 模板图像

将 Xbox UI 截图放入 `templates/` 目录：

| 文件名 | 用途 |
|--------|------|
| xbox_home.png | 主页 |
| xbox_login.png | 登录页 |
| game_hub.png | 游戏中心 |
| account_{gamertag}.png | 账号头像 |

---

## 常见问题

| 问题 | 解决方案 |
|------|----------|
| 启动报错"DLL not found" | 安装 [VC++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) |
| 无法连接服务器 | 检查 agent.yaml 中的 base_url 是否正确 |
| 模板匹配不工作 | 确认 templates/ 目录有对应截图 |
| 程序无响应 | 查看 logs/agent.log 排查错误 |
