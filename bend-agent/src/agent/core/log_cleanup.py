"""
日志文件定期清理
================

Agent 启动时扫描 logs/ 目录，删除超过保留期的旧日志文件。
所有日志文件（agent.log、task_*.log、account_*.log、heartbeat_*.log 及其轮转备份）
统一按文件修改时间清理。

清理策略:
- 默认保留 30 天
- 可通过环境变量 AGENT_LOG_MAX_DAYS 调整
- 仅清理 .log / .log.1 / .log.2 ... 等日志文件,不影响其他文件
"""

import os
import time
from pathlib import Path


def cleanup_old_logs(log_dir: str, max_age_days: int = 30) -> int:
    """
    删除超过 max_age_days 天的旧日志文件。

    参数:
        log_dir:       日志目录路径
        max_age_days:  保留天数，默认 30

    返回:
        int  已删除的文件数
    """
    env_max_days = os.environ.get("AGENT_LOG_MAX_DAYS")
    if env_max_days:
        try:
            max_age_days = int(env_max_days)
        except ValueError:
            pass

    if not os.path.isdir(log_dir):
        return 0

    now = time.time()
    cutoff = now - (max_age_days * 86400)
    deleted = 0

    try:
        for entry in os.scandir(log_dir):
            if not entry.is_file():
                continue
            name = entry.name
            # 仅清理日志文件及其轮转备份 (.log, .log.1, .log.2, ...)
            if not (name.endswith('.log') or '.log.' in name):
                continue
            try:
                mtime = entry.stat().st_mtime
                if mtime < cutoff:
                    os.remove(entry.path)
                    deleted += 1
            except OSError:
                pass
    except OSError:
        pass

    return deleted
