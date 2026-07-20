# 部署入口

本项目支持两种部署方式，按需求选择：

## 🐳 Docker 部署 → [docker/](docker/)

适合：本地开发、SIT 测试、生产服务器（总控 Docker 部署）。

- **一键启动**：`docker/start-dev.ps1` / `start-sit.ps1` / `start-prod.ps1`
- **环境变量**：分层覆盖 —— `docker/.env`（基础）+ `.env.sit` / `.env.prod`（差异覆盖）
- **编排文件**：`docker/docker-compose.yml`（总控全栈）、`docker/docker-compose-tenant.yml`（分控 Docker）

## 📦 绿色生产包部署 → [standalone/](standalone/)

适合：给商户分发 Windows 安装包（总控 / 分控 / Agent），通过 Inno Setup 打包为 `.exe`。

> 📦 完整打包流程、前置准备、常见问题见 **[../BUILD.md](../BUILD.md)** 。

- **三包命令**：
  ```powershell
  powershell -File deploy\standalone\master\build-master-package.ps1   # 总控
  powershell -File deploy\standalone\tenant\build-tenant-package.ps1   # 分控
  powershell -File deploy\standalone\agent\build-agent-package.ps1     # Agent
  ```
- **前置准备**：green 资源放入 `deploy/standalone/staging/base/`（jre/mysql/redis/nginx/nssm.exe）
- **产物**：`deploy/standalone/{master,tenant,agent}/Output/` 下 `.exe` 安装包

## 本地三端验证

在同一台机器上验证总控 + 分控 + Agent 三层架构，参考 [standalone/local-dev-verify.md](standalone/local-dev-verify.md)。
