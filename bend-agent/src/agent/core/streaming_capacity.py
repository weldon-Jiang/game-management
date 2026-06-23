"""串流 + Step4 自动化并发容量测算（对齐弹性串流 spec §4）。"""

from __future__ import annotations

from dataclasses import dataclass

# 单路串流 + Step4 + 默认开窗（spec §4.1）
MEMORY_PER_TASK_MB = 300
CPU_CORES_PER_TASK = 0.5
SAFETY_FACTOR = 0.65
SYSTEM_RESERVE_MB = 4096


@dataclass(frozen=True)
class CapacityInputs:
    """硬件输入；max_gpu_slots 仅作信息字段，不限制总任务槽（超出走 CPU 解码）。"""

    cpu_count: int
    total_memory_mb: int
    max_gpu_slots: int = 0


@dataclass(frozen=True)
class CapacityEstimate:
    hardware_estimate: int
    max_by_cpu: int
    max_by_memory: int
    max_by_gpu: int


def estimate_hardware_capacity(inputs: CapacityInputs) -> CapacityEstimate:
    """
    按 CPU / 内存估算可同时承载的串流+Step4 路数。

    GPU 槽位不纳入 min()：max_concurrent_gpu 只限制 GPU 解码路数，其余降级 CPU。
    """
    cpu = max(1, int(inputs.cpu_count))
    mem = max(0, int(inputs.total_memory_mb))
    gpu_slots = max(0, int(inputs.max_gpu_slots))

    max_by_cpu = int(cpu / CPU_CORES_PER_TASK * SAFETY_FACTOR)
    available_mem = max(0, mem - SYSTEM_RESERVE_MB)
    max_by_memory = int(available_mem / MEMORY_PER_TASK_MB)
    max_by_gpu = gpu_slots

    hardware = max(1, min(max_by_cpu, max_by_memory))
    return CapacityEstimate(
        hardware_estimate=hardware,
        max_by_cpu=max_by_cpu,
        max_by_memory=max_by_memory,
        max_by_gpu=max_by_gpu,
    )


def resolve_declared_capacity(
    inputs: CapacityInputs,
    *,
    min_concurrent: int = 20,
    capacity_cap: int = 50,
) -> int:
    """
    declared = max(min_concurrent, min(hardware_estimate, capacity_cap))

    capacity_cap <= 0 表示不封顶（仅硬件与 min_concurrent 约束）。
    硬件不足 min_concurrent 时仍返回 min_concurrent（启动告警由 central_manager 处理）。
    """
    estimate = estimate_hardware_capacity(inputs)
    floor = max(1, int(min_concurrent))
    raw = max(floor, estimate.hardware_estimate)
    cap = int(capacity_cap)
    if cap > 0:
        raw = min(raw, cap)
    return raw
