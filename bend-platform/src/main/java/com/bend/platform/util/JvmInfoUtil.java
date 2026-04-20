package com.bend.platform.util;

import java.lang.management.ManagementFactory;
import java.lang.management.MemoryMXBean;
import java.lang.management.MemoryUsage;
import java.lang.management.ThreadMXBean;

/**
 * JVM信息工具类
 *
 * 功能说明：
 * - 提供JVM运行时信息采集
 * - 用于系统监控和诊断
 */
public class JvmInfoUtil {

    private static final MemoryMXBean memoryMXBean = ManagementFactory.getMemoryMXBean();
    private static final ThreadMXBean threadMXBean = ManagementFactory.getThreadMXBean();

    /**
     * 获取JVM内存信息
     */
    public static MemoryInfo getMemoryInfo() {
        MemoryUsage heapUsage = memoryMXBean.getHeapMemoryUsage();
        MemoryUsage nonHeapUsage = memoryMXBean.getNonHeapMemoryUsage();

        return MemoryInfo.builder()
                .heapInit(heapUsage.getInit())
                .heapUsed(heapUsage.getUsed())
                .heapCommitted(heapUsage.getCommitted())
                .heapMax(heapUsage.getMax())
                .nonHeapInit(nonHeapUsage.getInit())
                .nonHeapUsed(nonHeapUsage.getUsed())
                .nonHeapCommitted(nonHeapUsage.getCommitted())
                .nonHeapMax(nonHeapUsage.getMax())
                .build();
    }

    /**
     * 获取线程信息
     */
    public static ThreadInfo getThreadInfo() {
        return ThreadInfo.builder()
                .currentThreadCount(threadMXBean.getThreadCount())
                .peakThreadCount(threadMXBean.getPeakThreadCount())
                .daemonThreadCount(threadMXBean.getDaemonThreadCount())
                .totalStartedThreadCount(threadMXBean.getTotalStartedThreadCount())
                .build();
    }

    /**
     * 获取GC信息
     */
    public static GCInfo getGCInfo() {
        return GCInfo.builder()
                .gcCount(threadMXBean.getThreadCount())
                .build();
    }

    @lombok.Data
    @lombok.Builder
    public static class MemoryInfo {
        private long heapInit;
        private long heapUsed;
        private long heapCommitted;
        private long heapMax;
        private long nonHeapInit;
        private long nonHeapUsed;
        private long nonHeapCommitted;
        private long nonHeapMax;
    }

    @lombok.Data
    @lombok.Builder
    public static class ThreadInfo {
        private int currentThreadCount;
        private int peakThreadCount;
        private int daemonThreadCount;
        private long totalStartedThreadCount;
    }

    @lombok.Data
    @lombok.Builder
    public static class GCInfo {
        private long gcCount;
    }
}
