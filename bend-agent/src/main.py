"""
Bend Agent - Main entry point
"""
import asyncio
import sys
import os
import argparse
from pathlib import Path

# 添加源代码目录到路径（仅在开发环境）
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.core.config import config
from agent.core.logger import get_logger
from agent.api.registration import RegistrationActivator
from agent.core.central_manager import CentralManager


class AgentRunner:
    """Agent runner with registration code activation"""

    def __init__(self):
        self.activator = RegistrationActivator()
        self.manager: CentralManager = None
        self.logger = get_logger('runner')

    async def run_with_activation(self):
        """Run with registration code activation if needed"""
        credentials = self.activator.get_credentials()

        if credentials is None:
            print("\n" + "=" * 50)
            print("  Bend Agent 首次运行需要激活")
            print("=" * 50)
            print("\n请输入商户注册码进行激活：")
            print("(注册码格式: AGENT-XXXX-XXXX-XXXX)")
            print()

            while True:
                code = input("注册码: ").strip()

                if not code:
                    print("注册码不能为空，请重新输入")
                    continue

                try:
                    credentials = await self.activator.activate(code)
                    print("\n激活成功！")
                    print(f"Agent ID: {credentials.agent_id}")
                    print(f"Merchant ID: {credentials.merchant_id}")
                    break
                except Exception as e:
                    print(f"\n激活失败: {e}")
                    print("请重新输入注册码，或按 Ctrl+C 退出\n")

        return credentials

    async def run(self, registration_code: str = None):
        """Run the agent"""
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
            credentials.agent_secret
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
            self.logger.info("Received shutdown signal")
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        finally:
            await self.shutdown()

        return True

    async def shutdown(self):
        """Graceful shutdown"""
        self.logger.info("Shutting down...")
        if self.manager:
            await self.manager.stop()
        self.logger.info("Shutdown complete")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Bend Agent - Xbox Automation Controller')
    parser.add_argument('--code', help='Registration code for activation')
    parser.add_argument('--config', help='Path to config file')
    args = parser.parse_args()

    if args.config:
        config.load(args.config)

    runner = AgentRunner()
    success = await runner.run(args.code)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
