"""
Bend Agent 主入口。
"""
import asyncio
import sys
import os
import argparse
from pathlib import Path

from agent.core.encoding_bootstrap import ensure_utf8_stdio

ensure_utf8_stdio()

# Windows：尽早设置 AppUserModelID，避免 SDL 串流窗口任务栏仍显示 python.exe 图标。
if sys.platform == "win32":
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "com.bend.agent.streamwindow"
        )
    except Exception:
        pass

# 添加源代码目录到路径（仅在开发环境）
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.core.config import get_config, load_config, AgentConfig
from agent.core.log_cleanup import cleanup_old_logs
from agent.core.logger import get_logger
from agent.core.paths import get_logs_dir
from agent.core.install_guard import (
    assert_single_install,
    InstallGuardError,
    migrate_install_marker_if_needed,
)
from agent.core.agent_uninstall import perform_agent_uninstall
from agent.api.registration import RegistrationActivator
from agent.core.central_manager import CentralManager


class AgentRunner:
    """带注册码激活的 Agent 运行器。"""

    def __init__(self):
        self.activator = RegistrationActivator()
        self.manager: CentralManager = None
        self.logger = get_logger('runner')

    async def run_with_activation(self):
        """首次运行自动发现分控并免注册码自动注册。"""
        credentials = self.activator.get_credentials()

        if credentials is None:
            # 分控架构:UDP 自动发现局域网分控地址
            from agent.core.config import get_config
            from agent.core.tenant_discovery import is_backend_url_placeholder, discover, write_discovered_url
            cfg = get_config()
            need_discover = is_backend_url_placeholder(getattr(cfg, 'backend_url', ''))

            if need_discover:
                print("\n正在局域网内搜索分控服务(UDP 广播,最多8秒)...")
                self.logger.info("backend.base_url 为占位,启动 UDP 分控发现...")
                found = discover(timeout=8.0)
                if not found:
                    print("\n" + "=" * 50)
                    print("  未发现分控服务,无法启动 Agent")
                    print("=" * 50)
                    print("请确认:")
                    print("  1. 本机所在局域网已安装并启动分控平台服务")
                    print("  2. 分控与本机在同一个局域网(同一网段)")
                    print("  3. 若先装 Agent 后装分控,请先安装分控平台再启动 Agent")
                    print("\nAgent 退出。请先安装分控平台服务后再运行 Agent。")
                    return None
                ip, port = found
                # 回写 agent.yaml
                reload_path = None
                for p in [os.path.join(os.path.dirname(__file__), '..', 'configs', 'agent.yaml')]:
                    p = os.path.normpath(p)
                    if os.path.exists(p):
                        reload_path = p
                        break
                if reload_path:
                    write_discovered_url(reload_path, ip, port)
                    from agent.core.config import load_config
                    load_config(reload_path)
                print(f"已发现分控服务: {ip}:{port}")

            # 免注册码自动注册
            print("\n正在向分控服务自动注册...")
            try:
                credentials = await self.activator.auto_register()
                print("自动注册成功!")
                print(f"Agent ID: {credentials.agent_id}")
                print(f"Merchant ID: {credentials.merchant_id}")
            except Exception as e:
                print(f"\n自动注册失败: {e}")
                print("请确认分控服务已正常启动且 license 校验通过。")
                return None

        return credentials

    async def run(self, registration_code: str = None):
        """运行 Agent。"""
        # 启动时清理超过 30 天的旧日志
        try:
            log_dir = get_logs_dir()
            deleted = cleanup_old_logs(log_dir, max_age_days=30)
            if deleted > 0:
                print(f"已清理 {deleted} 个过期日志文件(保留 30 天)")
        except Exception:
            pass  # 清理失败不影响主流程

        self.logger.info("Initializing Bend Agent...")

        credentials = None

        if registration_code:
            try:
                credentials = await self.activator.activate(registration_code)
                print(f"Agent activated with code: {registration_code}")
            except Exception as e:
                print(f"Activation failed: {e}")
                return False
        else:
            try:
                credentials = await self.run_with_activation()
            except KeyboardInterrupt:
                print("\n\n取消激活，程序退出")
                return False

        self.logger.info(f"Starting agent: {credentials.agent_id}")

        self.manager = CentralManager(
            credentials.agent_id,
            credentials.agent_secret,
            credentials.registration_code
        )

        try:
            started = await self.manager.start()
            if not started:
                self.logger.error("Failed to start agent")
                return False

            self.logger.info("Agent is running. Press Ctrl+C to stop.")

            while True:
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            self.logger.info("Received cancellation signal")
            raise  # Re-raise to let caller handle it
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        finally:
            # 安全地关闭 manager
            try:
                if self.manager and self.manager._running:
                    await self.stop_manager()
            except Exception as e:
                self.logger.error(f"Error during shutdown: {e}")
            self.logger.info("Shutdown complete")

    async def stop_manager(self):
        """停止 manager 的安全方法"""
        try:
            if self.manager:
                await self.manager.stop()
        except Exception as e:
            self.logger.error(f"Error stopping manager: {e}")


async def main():
    """Main entry point"""
    import os

    parser = argparse.ArgumentParser(description='Bend Agent - Xbox Automation Controller')
    parser.add_argument('--code', help='Registration code for activation')
    parser.add_argument('--config', help='Path to config file')
    parser.add_argument(
        '--uninstall',
        action='store_true',
        help='Uninstall local Agent (notify platform, clear credentials and registry)',
    )
    args = parser.parse_args()

    # 自动加载配置文件
    config_loaded = False
    if args.config:
        # 使用命令行指定的配置文件
        from agent.core.config import load_config
        load_config(args.config)
        config_loaded = True
    else:
        # 自动检测配置文件
        from agent.core.config import load_config
        possible_paths = [
            os.path.join(os.path.dirname(__file__), '..', 'configs', 'agent.yaml'),
            os.path.join(os.path.dirname(__file__), '..', '..', 'configs', 'agent.yaml'),
        ]
        for config_path in possible_paths:
            config_path = os.path.normpath(config_path)
            if os.path.exists(config_path):
                print(f"Loading config from: {config_path}")
                load_config(config_path)
                config_loaded = True
                break

    logger = get_logger('runner')

    if args.uninstall:
        try:
            await perform_agent_uninstall(reason="用户主动卸载")
            print("\n卸载完成。本机 Agent 安装标记与凭证已清除，可重新安装。")
            return 0
        except Exception as e:
            logger.error(f"Uninstall failed: {e}")
            print(f"\n卸载失败: {e}")
            return 1

    try:
        assert_single_install()
    except InstallGuardError as exc:
        print(f"\n{exc}")
        return 1

    activator = RegistrationActivator()
    migrate_install_marker_if_needed(activator.has_credentials())

    runner = AgentRunner()
    try:
        success = await runner.run(args.code)
        return 0 if success else 1
    except KeyboardInterrupt:
        runner.logger.info("Keyboard interrupt received, shutting down...")
        return 0
    except Exception as e:
        runner.logger.error(f"Unexpected error: {e}")
        return 1
    finally:
        # 确保 shutdown 被调用（包括KeyboardInterrupt时）
        # 使用shield保护stop_manager不被取消
        try:
            await asyncio.shield(runner.stop_manager())
        except Exception as e:
            runner.logger.error(f"Error during shutdown: {e}")


if __name__ == '__main__':
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nShutdown requested. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
