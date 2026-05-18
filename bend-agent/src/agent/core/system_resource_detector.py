"""
系统资源检测模块
===============

功能：
- 获取系统CPU核心数
- 获取系统内存信息
- 根据系统资源推荐最大并发数
- 支持动态调整并发配置

作者：技术团队
版本：1.0
"""

import os
import sys
import platform
from typing import Dict, Tuple, Optional

try:
    import psutil
except ImportError:
    psutil = None


class SystemResourceDetector:
    """
    系统资源检测器
    
    功能：
    1. 检测CPU核心数
    2. 检测内存大小
    3. 检测可用内存
    4. 计算推荐并发数
    """

    @classmethod
    def get_cpu_count(cls) -> int:
        """
        获取CPU核心数
        
        返回：
        - CPU逻辑核心数
        """
        return os.cpu_count() or 4

    @classmethod
    def get_memory_info(cls) -> Tuple[int, int]:
        """
        获取内存信息
        
        返回：
        - (总内存MB, 可用内存MB)
        """
        if psutil:
            mem = psutil.virtual_memory()
            return (mem.total // (1024 ** 2), mem.available // (1024 ** 2))
        
        # 备选方案（Windows）
        try:
            if platform.system() == 'Windows':
                import ctypes
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                return (
                    stat.ullTotalPhys // (1024 ** 2),
                    stat.ullAvailPhys // (1024 ** 2)
                )
        except:
            pass
        
        # 默认值
        return (8192, 4096)  # 8GB总内存，4GB可用

    @classmethod
    def get_disk_info(cls) -> Tuple[int, int]:
        """
        获取磁盘信息
        
        返回：
        - (总空间MB, 可用空间MB)
        """
        if psutil:
            disk = psutil.disk_usage('.')
            return (disk.total // (1024 ** 2), disk.free // (1024 ** 2))
        
        return (100000, 50000)  # 默认100GB总空间，50GB可用

    @classmethod
    def recommend_concurrent_tasks(
        cls,
        accounts_count: int,
        browser_memory_per_instance: int = 150,  # MB
        cpu_cores_per_task: float = 0.2,  # 每个任务使用的CPU核心比例
        safety_factor: float = 0.7  # 安全系数
    ) -> int:
        """
        根据系统资源推荐最大并发任务数
        
        参数：
        - accounts_count: 流媒体账号总数
        - browser_memory_per_instance: 每个浏览器实例预估内存（MB）
        - cpu_cores_per_task: 每个任务使用的CPU核心比例
        - safety_factor: 安全系数（预留资源给系统）
        
        返回：
        - 推荐的最大并发任务数
        
        说明：
        - 使用总内存（物理内存配置）计算，而非可用内存
        - 这样最大并发数是固定的，不会随系统运行而变化
        """
        cpu_count = cls.get_cpu_count()
        total_mem_mb, _ = cls.get_memory_info()
        
        # 基于CPU计算
        max_by_cpu = int(cpu_count / cpu_cores_per_task * safety_factor)
        
        # 基于总内存计算（预留2GB给系统和其他应用）
        # 使用总内存而非可用内存，确保并发数固定
        available_for_browsers = max(0, total_mem_mb - 2048)
        max_by_memory = int(available_for_browsers / browser_memory_per_instance)
        
        # 基于账号数量
        max_by_accounts = accounts_count
        
        # 取最小值
        recommended = min(max_by_cpu, max_by_memory, max_by_accounts)
        
        # 确保至少1个并发
        recommended = max(1, recommended)
        
        return recommended

    @classmethod
    def recommend_max_concurrent_tasks(
        cls,
        browser_memory_per_instance: int = 150,  # MB
        cpu_cores_per_task: float = 0.2,  # 每个任务使用的CPU核心比例
        safety_factor: float = 0.7  # 安全系数
    ) -> int:
        """
        根据系统资源推荐最大并发任务数（不依赖账号数量）
        
        参数：
        - browser_memory_per_instance: 每个浏览器实例预估内存（MB）
        - cpu_cores_per_task: 每个任务使用的CPU核心比例
        - safety_factor: 安全系数（预留资源给系统）
        
        返回：
        - 推荐的最大并发任务数
        
        说明：
        - 使用总内存（物理内存配置）计算，而非可用内存
        - 这样最大并发数是固定的，不会随系统运行而变化
        """
        cpu_count = cls.get_cpu_count()
        total_mem_mb, _ = cls.get_memory_info()
        
        # 基于CPU计算
        max_by_cpu = int(cpu_count / cpu_cores_per_task * safety_factor)
        
        # 基于总内存计算（预留2GB给系统和其他应用）
        # 使用总内存而非可用内存，确保并发数固定
        available_for_browsers = max(0, total_mem_mb - 2048)
        max_by_memory = int(available_for_browsers / browser_memory_per_instance)
        
        # 取最小值
        recommended = min(max_by_cpu, max_by_memory)
        
        # 确保至少1个并发，最多50个
        recommended = max(1, min(50, recommended))
        
        return recommended
    
    @classmethod
    def get_system_info(cls) -> Dict[str, any]:
        """
        获取完整的系统信息
        
        返回：
        - 系统信息字典
        """
        cpu_count = cls.get_cpu_count()
        total_mem, available_mem = cls.get_memory_info()
        total_disk, free_disk = cls.get_disk_info()
        
        return {
            'platform': platform.system(),
            'platform_version': platform.version(),
            'python_version': sys.version,
            'cpu_count': cpu_count,
            'total_memory_mb': total_mem,
            'available_memory_mb': available_mem,
            'total_disk_mb': total_disk,
            'free_disk_mb': free_disk,
            'architecture': platform.architecture()[0]
        }

    @classmethod
    def print_system_info(cls):
        """打印系统信息"""
        info = cls.get_system_info()
        print("=" * 50)
        print("系统资源信息")
        print("=" * 50)
        print(f"操作系统: {info['platform']} {info['platform_version']}")
        print(f"Python版本: {info['python_version'][:20]}")
        print(f"CPU核心数: {info['cpu_count']}")
        print(f"总内存: {info['total_memory_mb'] / 1024:.1f} GB")
        print(f"可用内存: {info['available_memory_mb'] / 1024:.1f} GB")
        print(f"总磁盘空间: {info['total_disk_mb'] / 1024:.1f} GB")
        print(f"可用磁盘空间: {info['free_disk_mb'] / 1024:.1f} GB")
        print("=" * 50)


def test_resource_detection():
    """测试系统资源检测"""
    SystemResourceDetector.print_system_info()
    
    # 测试不同账号数量的推荐并发数
    print("\n推荐并发数测试：")
    for accounts in [10, 20, 30, 40, 50, 100]:
        recommended = SystemResourceDetector.recommend_concurrent_tasks(accounts)
        print(f"账号数: {accounts:3d} → 推荐并发: {recommended:3d}")


if __name__ == "__main__":
    test_resource_detection()
