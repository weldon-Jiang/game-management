# Bend Agent 开发者打包指南

## 打包前准备

### 1. 安装打包工具

```bash
pip install pyarmor pyinstaller
```

### 2. 确保代码完整

项目结构应包含：
```
bend-agent/
├── configs/
│   └── agent.yaml
├── templates/          # 截图模板（可选）
├── src/
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── api/
│   │   ├── core/
│   │   ├── game/
│   │   ├── input/
│   │   ├── scene/
│   │   ├── vision/
│   │   └── windows/
│   └── main.py
├── requirements.txt
└── scripts/
    └── build.bat
```

## 打包步骤

### 方式一：使用打包脚本（推荐）

```bash
cd bend-agent
scripts\build.bat
```

打包完成后，`dist\release\` 目录即为可分发的安装包。

### 方式二：手动打包

```bash
# 1. 安装依赖
pip install -r requirements.txt
pip install pyarmor pyinstaller

# 2. 加密代码
pyarmor gen --output dist/agent --assert all --assert call src/

# 3. 复制配置和模板
copy /Y configs\* dist\agent\
if exist templates xcopy /S /Q templates\* dist\agent\templates\

# 4. 打包成 exe
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

## 商户分发包结构

打包完成后，商户收到的文件应包含：

```
BendAgent/
├── BendAgent.exe      # 主程序
├── agent.yaml        # 配置文件
├── templates/        # 模板目录（可选）
└── README.txt        # 使用说明
```

## 商户安装指南

### 1. 解压安装包

将 `BendAgent.zip` 解压到任意目录，例如：`C:\BendAgent`

### 2. 修改配置文件

用记事本打开 `agent.yaml`，修改服务器地址：

```yaml
backend:
  base_url: "http://你的平台域名:8080"
  ws_url: "ws://你的平台域名:8080"
```

### 3. 运行程序

双击 `BendAgent.exe`

### 4. 绑定 Agent

1. 登录平台管理后台
2. 进入「Agent管理」
3. 点击「添加Agent」
4. 记录生成的 Agent ID 和 Secret
5. 程序运行后自动完成绑定

## 高级配置

### 模板匹配灵敏度

如果模板匹配不灵敏，可调整阈值：

```yaml
template:
  threshold: 0.7  # 降低灵敏度（更易匹配）
  # threshold: 0.9  # 提高灵敏度（更严格）
```

### 添加游戏截图模板

将游戏截图放入 `templates/` 目录：

| 文件名 | 用途 |
|--------|------|
| xbox_home.png | Xbox主页 |
| xbox_login.png | 登录页 |
| game_ready.png | 游戏就绪 |
| account_xxx.png | 账号头像 |

### 日志查看

日志文件位置：`程序目录\logs\agent.log`

如遇问题，可将日志发送给技术支持。

## 常见问题

| 问题 | 解决方案 |
|------|----------|
| 启动报错"DLL not found" | 安装 [VC++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) |
| 无法连接服务器 | 检查 agent.yaml 中的 base_url 是否正确 |
| 模板匹配不工作 | 确认 templates/ 目录有对应截图 |
| 程序无响应 | 查看 logs/agent.log 排查错误 |

## 版本更新

更新时只需替换 `BendAgent.exe` 文件，配置文件和模板可保留。
