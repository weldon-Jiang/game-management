package com.bend.platform.service;

import com.bend.platform.entity.SystemMetrics;
import com.bend.platform.repository.SystemMetricsMapper;
import com.bend.platform.util.JvmInfoUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.lang.management.ManagementFactory;
import java.lang.management.OperatingSystemMXBean;
import java.net.InetAddress;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 系统监控服务
 *
 * 功能说明：
 * - 采集系统各项性能指标
 * - 存储历史指标数据
 * - 提供实时监控数据接口
 *
 * 监控指标：
 * - JVM指标：内存、GC、线程数
 * - 系统指标：CPU、内存、磁盘
 * - 业务指标：在线Agent数、任务数、成功率
 *
 * 采集策略：
 * - 每分钟采集一次JVM和系统指标
 * - 每小时汇总一次业务指标
 * - 保留最近30天的数据
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class SystemMonitorService {

    private final SystemMetricsMapper metricsMapper;

    // 累计请求数
    private static final AtomicInteger totalRequests = new AtomicInteger(0);
    // 成功请求数
    private static final AtomicInteger successRequests = new AtomicInteger(0);
    // 失败请求数
    private static final AtomicInteger failedRequests = new AtomicInteger(0);

    /**
     * 记录API请求
     *
     * 功能说明：
     * - 在Controller层调用统计
     * - 用于计算请求成功率和响应时间
     *
     * 参数说明：
     * - success: 请求是否成功
     */
    public void recordRequest(boolean success) {
        totalRequests.incrementAndGet();
        if (success) {
            successRequests.incrementAndGet();
        } else {
            failedRequests.incrementAndGet();
        }
    }

    /**
     * 获取当前JVM信息
     *
     * 返回值：JVM信息对象
     */
    public JvmInfo getJvmInfo() {
        Runtime runtime = Runtime.getRuntime();
        long totalMemory = runtime.totalMemory();
        long freeMemory = runtime.freeMemory();
        long usedMemory = totalMemory - freeMemory;
        long maxMemory = runtime.maxMemory();

        // 获取OS信息
        OperatingSystemMXBean osBean = ManagementFactory.getOperatingSystemMXBean();

        return JvmInfo.builder()
                .totalMemory(formatBytes(totalMemory))
                .freeMemory(formatBytes(freeMemory))
                .usedMemory(formatBytes(usedMemory))
                .maxMemory(formatBytes(maxMemory))
                .totalMemoryBytes(totalMemory)
                .freeMemoryBytes(freeMemory)
                .usedMemoryBytes(usedMemory)
                .maxMemoryBytes(maxMemory)
                .memoryUsagePercent((double) usedMemory / totalMemory * 100)
                .availableProcessors(runtime.availableProcessors())
                .systemLoadAverage(osBean.getSystemLoadAverage())
                .osName(System.getProperty("os.name"))
                .osVersion(System.getProperty("os.version"))
                .javaVersion(System.getProperty("java.version"))
                .uptime(ManagementFactory.getRuntimeMXBean().getUptime())
                .build();
    }

    /**
     * 获取当前系统信息
     *
     * 返回值：系统信息对象
     */
    public SystemInfo getSystemInfo() {
        try {
            OperatingSystemMXBean osBean = ManagementFactory.getOperatingSystemMXBean();
            Runtime runtime = Runtime.getRuntime();

            // 获取CPU使用率（近似值）
            double cpuUsage = osBean.getSystemLoadAverage();

            // 获取内存信息
            long totalMemory = runtime.totalMemory();
            long freeMemory = runtime.freeMemory();

            // 获取主机名和IP
            InetAddress localHost = InetAddress.getLocalHost();
            String hostName = localHost.getHostName();
            String hostIp = localHost.getHostAddress();

            return SystemInfo.builder()
                    .hostName(hostName)
                    .hostIp(hostIp)
                    .cpuUsagePercent(cpuUsage)
                    .cpuCoreCount(osBean.getAvailableProcessors())
                    .totalMemory(formatBytes(totalMemory))
                    .freeMemory(formatBytes(freeMemory))
                    .totalMemoryBytes(totalMemory)
                    .freeMemoryBytes(freeMemory)
                    .memoryUsagePercent((double)(totalMemory - freeMemory) / totalMemory * 100)
                    .osName(System.getProperty("os.name"))
                    .osVersion(System.getProperty("os.version"))
                    .build();
        } catch (Exception e) {
            log.error("获取系统信息失败", e);
            return null;
        }
    }

    /**
     * 获取业务统计信息
     *
     * 返回值：业务统计数据
     */
    public BusinessStats getBusinessStats() {
        int total = totalRequests.get();
        int success = successRequests.get();
        int failed = failedRequests.get();
        double successRate = total > 0 ? (double) success / total * 100 : 0;

        return BusinessStats.builder()
                .totalRequests(total)
                .successRequests(success)
                .failedRequests(failed)
                .successRate(successRate)
                .build();
    }

    /**
     * 定时任务：采集JVM和系统指标
     *
     * 执行频率：每分钟
     *
     * 功能说明：
     * - 采集JVM内存使用情况
     * - 采集系统CPU和内存使用情况
     * - 存储到数据库供历史查询
     */
    @Scheduled(fixedRate = 60000) // 每分钟
    public void collectMetrics() {
        try {
            JvmInfo jvmInfo = getJvmInfo();
            SystemInfo systemInfo = getSystemInfo();

            // 保存JVM内存指标
            saveMetric("jvm", "memory_used", (double) jvmInfo.getUsedMemoryBytes(),
                    "bytes", getHostName(), "JVM已使用内存");
            saveMetric("jvm", "memory_free", (double) jvmInfo.getFreeMemoryBytes(),
                    "bytes", getHostName(), "JVM空闲内存");
            saveMetric("jvm", "memory_usage_percent", jvmInfo.getMemoryUsagePercent(),
                    "%", getHostName(), "JVM内存使用率");

            if (systemInfo != null) {
                // 保存系统CPU指标
                saveMetric("system", "cpu_usage_percent", systemInfo.getCpuUsagePercent(),
                        "%", systemInfo.getHostName(), "系统CPU使用率");

                // 保存系统内存指标
                saveMetric("system", "memory_usage_percent", systemInfo.getMemoryUsagePercent(),
                        "%", systemInfo.getHostName(), "系统内存使用率");
            }

            log.debug("系统指标采集完成 - JVM内存: {}, CPU: {}",
                    jvmInfo.getUsedMemory(), systemInfo != null ? systemInfo.getCpuUsagePercent() : "N/A");

        } catch (Exception e) {
            log.error("采集系统指标失败", e);
        }
    }

    /**
     * 保存指标到数据库
     */
    private void saveMetric(String type, String name, Double value, String unit, String host, String desc) {
        try {
            SystemMetrics metric = new SystemMetrics();
            metric.setMetricType(type);
            metric.setMetricName(name);
            metric.setValue(value);
            metric.setUnit(unit);
            metric.setHostName(host);
            metric.setDescription(desc);
            metric.setRecordedTime(LocalDateTime.now());
            metricsMapper.insert(metric);
        } catch (Exception e) {
            log.error("保存指标失败: {} - {}", name, e.getMessage());
        }
    }

    /**
     * 获取最近N小时的指标趋势
     *
     * 参数说明：
     * - hours: 小时数
     * - metricName: 指标名称
     *
     * 返回值：指标历史列表
     */
    public List<SystemMetrics> getMetricsTrend(int hours, String metricName) {
        LocalDateTime startTime = LocalDateTime.now().minusHours(hours);
        return metricsMapper.selectTrend(metricName, startTime);
    }

    /**
     * 重置统计计数器
     *
     * 使用场景：
     * - 统计周期结束时重置
     * - 系统重启时重置
     */
    public void resetCounters() {
        totalRequests.set(0);
        successRequests.set(0);
        failedRequests.set(0);
        log.info("统计计数器已重置");
    }

    /**
     * 格式化字节数
     */
    private String formatBytes(long bytes) {
        if (bytes < 1024) return bytes + " B";
        int exp = (int) (Math.log(bytes) / Math.log(1024));
        String pre = "KMGTPE".charAt(exp - 1) + "B";
        return String.format("%.2f %s", bytes / Math.pow(1024, exp), pre);
    }

    private String getHostName() {
        try {
            return InetAddress.getLocalHost().getHostName();
        } catch (Exception e) {
            return "unknown";
        }
    }

    /**
     * JVM信息内部类
     */
    @lombok.Data
    @lombok.Builder
    public static class JvmInfo {
        private String totalMemory;
        private String freeMemory;
        private String usedMemory;
        private String maxMemory;
        private long totalMemoryBytes;
        private long freeMemoryBytes;
        private long usedMemoryBytes;
        private long maxMemoryBytes;
        private double memoryUsagePercent;
        private int availableProcessors;
        private double systemLoadAverage;
        private String osName;
        private String osVersion;
        private String javaVersion;
        private long uptime;
    }

    /**
     * 系统信息内部类
     */
    @lombok.Data
    @lombok.Builder
    public static class SystemInfo {
        private String hostName;
        private String hostIp;
        private double cpuUsagePercent;
        private int cpuCoreCount;
        private String totalMemory;
        private String freeMemory;
        private long totalMemoryBytes;
        private long freeMemoryBytes;
        private double memoryUsagePercent;
        private String osName;
        private String osVersion;
    }

    /**
     * 业务统计内部类
     */
    @lombok.Data
    @lombok.Builder
    public static class BusinessStats {
        private int totalRequests;
        private int successRequests;
        private int failedRequests;
        private double successRate;
    }
}
