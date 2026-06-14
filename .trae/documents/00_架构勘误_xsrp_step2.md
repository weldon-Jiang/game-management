# 架构勘误：Step2–3 串流栈（2026-06-13）

本文档为 `.trae/documents/` 历史设计稿的**当前实现对照**。若下文其他文件仍出现 SmartGlass LAN 主链路或 `step2_xbox_streaming.py`，以本节为准。

## 生产热路径（bend-agent）

| 步骤 | 入口文件 | 职责 |
|------|----------|------|
| Step1 | `bend-agent/src/agent/automation/step1_xblive_login.py`（`auth/step1_router`） | xblive 认证 + GSSV/Xbox Token |
| Step2 | `bend-agent/src/agent/automation/step2_xsrp.py` → `xbox/step2_xsrp_connect.py` | GSSV 云端发现 + play/WebRTC 握手 |
| Step3 | `bend-agent/src/agent/automation/step3_xsrp.py`（`auth/step3_router`） | WebRTC 帧捕获 + SDL 窗口 + DataChannel 输入 |
| Step4 | `bend-agent/src/agent/automation/step4_game_automation.py` | 游戏自动化 |

**对齐参考**：`D:\auto-xbox\streaming\xsrp.py` OpenStreaming 的 GSSV/WebRTC 段（Agent 为 Python aiortc 实现）。

## 已废弃 / 非热路径

| 历史描述 | 现状 |
|----------|------|
| `step2_xbox_streaming.py` | **已删除**；由 `step2_xsrp.py` 替代 |
| `step3_streaming_init.py`（SmartGlass+pygame 主路径） | **非热路径**；生产用 `step3_xsrp.py` |
| SmartGlass TCP:5050 串流 + PlaySession 主链路 | **非 Step2–3 主路径**；代码仍可能存在供调试 |
| SmartGlass UDP 5050 | **保留**：LAN 发现 / 唤醒兜底（`xbox/xbox_discovery.py`） |

## 输入通道

- **生产**：WebRTC DataChannel → `input/controller_protocol.py`（`ControllerProtocol`）
- **非生产主路径**：SmartGlass TCP 发送手柄（历史文档中的 pygame+SmartGlass 描述）

## 权威文档

- `AGENTS.md`（v3.5+）
- `bend-agent/README.md`
- `bend-agent/ARCHITECTURE.md`
