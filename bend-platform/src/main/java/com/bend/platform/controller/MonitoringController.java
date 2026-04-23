package com.bend.platform.controller;

import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.SystemAlert;
import com.bend.platform.entity.SystemMetrics;
import com.bend.platform.service.AlertService;
import com.bend.platform.service.SystemMonitorService;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 系统监控控制器
 *
 * 功能说明：
 * - 提供系统监控指标查询接口
 * - 提供告警管理接口
 * - 提供JVM和系统信息接口
 *
 * 主要接口：
 * - GET /monitoring/jvm - 获取JVM信息
 * - GET /monitoring/system - 获取系统信息
 * - GET /monitoring/stats - 获取业务统计
 * - GET /monitoring/alerts - 获取告警列表
 * - POST /monitoring/alerts/{id}/acknowledge - 确认告警
 * - POST /monitoring/alerts/{id}/resolve - 解决告警
 */
@Slf4j
@RestController
@RequestMapping("/api/monitoring")
@RequiredArgsConstructor
public class MonitoringController {

    private final SystemMonitorService monitorService;
    private final AlertService alertService;

    /**
     * 获取JVM信息
     *
     * @return JVM信息（内存、GC、线程等）
     */
    @GetMapping("/jvm")
    public ApiResponse<SystemMonitorService.JvmInfo> getJvmInfo() {
        return ApiResponse.success(monitorService.getJvmInfo());
    }

    /**
     * 获取系统信息
     *
     * @return 系统信息（CPU、内存、磁盘等）
     */
    @GetMapping("/system")
    public ApiResponse<SystemMonitorService.SystemInfo> getSystemInfo() {
        return ApiResponse.success(monitorService.getSystemInfo());
    }

    /**
     * 获取业务统计信息
     *
     * @return 业务统计数据（在线Agent数、任务数等）
     */
    @GetMapping("/stats")
    public ApiResponse<SystemMonitorService.BusinessStats> getBusinessStats() {
        return ApiResponse.success(monitorService.getBusinessStats());
    }

    /**
     * 获取监控指标趋势
     *
     * @param hours      查询时间范围（小时）
     * @param metricName  指标名称
     * @return 指标趋势数据列表
     */
    @GetMapping("/metrics/trend")
    public ApiResponse<List<Map<String, Object>>> getMetricsTrend(
            @RequestParam(defaultValue = "1") int hours,
            @RequestParam String metricName) {

        List<SystemMetrics> metrics = monitorService.getMetricsTrend(hours, metricName);
        List<Map<String, Object>> result = new ArrayList<>();
        for (SystemMetrics metric : metrics) {
            Map<String, Object> dataPoint = new HashMap<>();
            dataPoint.put("time", metric.getRecordedTime().toString());
            dataPoint.put("value", metric.getValue());
            result.add(dataPoint);
        }
        return ApiResponse.success(result);
    }

    /**
     * 获取未处理的告警列表
     *
     * @return 未处理告警列表
     */
    @GetMapping("/alerts")
    public ApiResponse<List<SystemAlert>> getUnresolvedAlerts() {
        return ApiResponse.success(alertService.getUnresolvedAlerts());
    }

    /**
     * 获取告警统计
     *
     * @return 告警统计数据
     */
    @GetMapping("/alerts/stats")
    public ApiResponse<Map<String, Long>> getAlertStats() {
        return ApiResponse.success(alertService.getAlertStats());
    }

    /**
     * 确认告警
     *
     * @param id 告警ID
     * @return 操作结果
     */
    @PostMapping("/alerts/{id}/acknowledge")
    public ApiResponse<Void> acknowledgeAlert(@PathVariable String id) {
        String userId = UserContext.getUserId();
        if (userId == null) {
            userId = "system";
        }
        alertService.acknowledgeAlert(id, userId);
        return ApiResponse.success("告警已确认", null);
    }

    /**
     * 解决告警
     *
     * @param id   告警ID
     * @param body 请求体（包含note备注）
     * @return 操作结果
     */
    @PostMapping("/alerts/{id}/resolve")
    public ApiResponse<Void> resolveAlert(
            @PathVariable String id,
            @RequestBody Map<String, String> body) {
        String userId = UserContext.getUserId();
        if (userId == null) {
            userId = "system";
        }
        String note = body.get("note");
        alertService.resolveAlert(id, userId, note);
        return ApiResponse.success("告警已解决", null);
    }

    /**
     * 忽略告警
     *
     * @param id 告警ID
     * @return 操作结果
     */
    @PostMapping("/alerts/{id}/ignore")
    public ApiResponse<Void> ignoreAlert(@PathVariable String id) {
        alertService.ignoreAlert(id);
        return ApiResponse.success("告警已忽略", null);
    }

    /**
     * 获取商户的告警列表
     *
     * @param merchantId       商户ID
     * @param includeResolved  是否包含已解决的告警
     * @return 告警列表
     */
    @GetMapping("/alerts/merchant/{merchantId}")
    public ApiResponse<List<SystemAlert>> getMerchantAlerts(
            @PathVariable String merchantId,
            @RequestParam(defaultValue = "false") boolean includeResolved) {
        return ApiResponse.success(alertService.getMerchantAlerts(merchantId, includeResolved));
    }
}