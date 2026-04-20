package com.bend.platform.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bend.platform.entity.SystemAlert;
import com.bend.platform.repository.SystemAlertMapper;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 系统告警服务
 *
 * 功能说明：
 * - 生成和管理系统告警
 * - 告警级别分类和通知
 * - 告警确认和处理流程
 *
 * 告警类型：
 * - AGENT_OFFLINE: Agent离线超过阈值
 * - TASK_FAILED: 任务连续失败
 * - HIGH_ERROR_RATE: 错误率过高
 * - HIGH_CPU: CPU使用率过高
 * - HIGH_MEMORY: 内存使用率过高
 * - XBOX_CONNECTION_FAILED: Xbox连接失败
 * - AUTH_FAILURE: 认证失败
 *
 * 通知方式：
 * - 日志记录（INFO/WARN/ERROR级别）
 * - 邮件通知（可扩展）
 * - WebHook通知（可扩展）
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AlertService {

    private final SystemAlertMapper alertMapper;
    private final ObjectMapper objectMapper = new ObjectMapper();

    // 告警阈值配置
    private static final int AGENT_OFFLINE_THRESHOLD_MINUTES = 5;
    private static final int TASK_FAILURE_THRESHOLD = 3;
    private static final double CPU_USAGE_THRESHOLD = 90.0;
    private static final double MEMORY_USAGE_THRESHOLD = 90.0;
    private static final double ERROR_RATE_THRESHOLD = 10.0;

    // 最近任务失败计数
    private int recentTaskFailures = 0;

    /**
     * 触发Agent离线告警
     */
    public void triggerAgentOfflineAlert(String agentId, String merchantId) {
        if (hasUnresolvedAlert(agentId, "AGENT_OFFLINE")) {
            return;
        }

        try {
            SystemAlert alert = new SystemAlert();
            alert.setAlertCode("ALERT-" + System.currentTimeMillis());
            alert.setAlertName("Agent离线告警");
            alert.setSeverity("HIGH");
            alert.setAlertType("AGENT_OFFLINE");
            alert.setMessage("Agent已离线超过" + AGENT_OFFLINE_THRESHOLD_MINUTES + "分钟");

            Map<String, Object> detailsMap = new HashMap<>();
            detailsMap.put("agentId", agentId);
            detailsMap.put("threshold", AGENT_OFFLINE_THRESHOLD_MINUTES);
            alert.setDetails(objectMapper.writeValueAsString(detailsMap));

            alert.setAgentId(agentId);
            alert.setMerchantId(merchantId);
            alert.setStatus("TRIGGERED");
            alert.setTriggeredAt(LocalDateTime.now());

            alertMapper.insert(alert);
            log.warn("【告警】Agent离线 - AgentID: {}, 商户: {}", agentId, merchantId);

            sendAlertNotification(alert);

        } catch (Exception e) {
            log.error("创建Agent离线告警失败", e);
        }
    }

    /**
     * 触发任务失败告警
     */
    public void triggerTaskFailedAlert(String taskId, String errorMessage) {
        recentTaskFailures++;

        if (recentTaskFailures >= TASK_FAILURE_THRESHOLD) {
            if (!hasUnresolvedAlert(null, "TASK_FAILED")) {
                try {
                    SystemAlert alert = new SystemAlert();
                    alert.setAlertCode("ALERT-" + System.currentTimeMillis());
                    alert.setAlertName("任务失败告警");
                    alert.setSeverity("MEDIUM");
                    alert.setAlertType("TASK_FAILED");
                    alert.setMessage("任务连续失败次数超过" + TASK_FAILURE_THRESHOLD + "次");

                    Map<String, Object> detailsMap = new HashMap<>();
                    detailsMap.put("recentFailures", recentTaskFailures);
                    detailsMap.put("threshold", TASK_FAILURE_THRESHOLD);
                    detailsMap.put("lastError", errorMessage);
                    alert.setDetails(objectMapper.writeValueAsString(detailsMap));

                    alert.setTaskId(taskId);
                    alert.setStatus("TRIGGERED");
                    alert.setTriggeredAt(LocalDateTime.now());

                    alertMapper.insert(alert);
                    log.warn("【告警】任务连续失败 - 次数: {}, 最后错误: {}", recentTaskFailures, errorMessage);

                    sendAlertNotification(alert);

                } catch (Exception e) {
                    log.error("创建任务失败告警失败", e);
                }
            }

            recentTaskFailures = 0;
        }
    }

    /**
     * 触发系统资源告警
     */
    public void triggerResourceAlert(String alertType, double currentValue, double threshold) {
        if (hasUnresolvedAlert(null, alertType)) {
            return;
        }

        try {
            String alertName = "HIGH_CPU".equals(alertType) ? "CPU使用率过高" : "内存使用率过高";
            String message = String.format("%s告警：当前%.1f%%，阈值%.1f%%", alertName, currentValue, threshold);

            SystemAlert alert = new SystemAlert();
            alert.setAlertCode("ALERT-" + System.currentTimeMillis());
            alert.setAlertName(alertName);
            alert.setSeverity("MEDIUM");
            alert.setAlertType(alertType);
            alert.setMessage(message);

            Map<String, Object> detailsMap = new HashMap<>();
            detailsMap.put("currentValue", currentValue);
            detailsMap.put("threshold", threshold);
            alert.setDetails(objectMapper.writeValueAsString(detailsMap));

            alert.setStatus("TRIGGERED");
            alert.setTriggeredAt(LocalDateTime.now());

            alertMapper.insert(alert);
            log.warn("【告警】{}", message);

            sendAlertNotification(alert);

        } catch (Exception e) {
            log.error("创建资源告警失败", e);
        }
    }

    /**
     * 触发Xbox连接失败告警
     */
    public void triggerXboxConnectionAlert(String xboxId, String merchantId, String errorMessage) {
        if (hasUnresolvedAlert(xboxId, "XBOX_CONNECTION_FAILED")) {
            return;
        }

        try {
            SystemAlert alert = new SystemAlert();
            alert.setAlertCode("ALERT-" + System.currentTimeMillis());
            alert.setAlertName("Xbox连接失败告警");
            alert.setSeverity("HIGH");
            alert.setAlertType("XBOX_CONNECTION_FAILED");
            alert.setMessage("Xbox主机连接失败");

            Map<String, Object> detailsMap = new HashMap<>();
            detailsMap.put("xboxId", xboxId);
            detailsMap.put("errorMessage", errorMessage);
            alert.setDetails(objectMapper.writeValueAsString(detailsMap));

            alert.setMerchantId(merchantId);
            alert.setStatus("TRIGGERED");
            alert.setTriggeredAt(LocalDateTime.now());

            alertMapper.insert(alert);
            log.error("【告警】Xbox连接失败 - XboxID: {}, 错误: {}", xboxId, errorMessage);

            sendAlertNotification(alert);

        } catch (Exception e) {
            log.error("创建Xbox连接告警失败", e);
        }
    }

    /**
     * 确认告警
     */
    public void acknowledgeAlert(String alertId, String acknowledgedBy) {
        SystemAlert alert = alertMapper.selectById(alertId);
        if (alert != null && "TRIGGERED".equals(alert.getStatus())) {
            alert.setStatus("ACKNOWLEDGED");
            alert.setAcknowledgedAt(LocalDateTime.now());
            alert.setAcknowledgedBy(acknowledgedBy);
            alertMapper.updateById(alert);
            log.info("告警已确认 - AlertID: {}, 确认人: {}", alertId, acknowledgedBy);
        }
    }

    /**
     * 解决告警
     */
    public void resolveAlert(String alertId, String resolvedBy, String note) {
        SystemAlert alert = alertMapper.selectById(alertId);
        if (alert != null && !"RESOLVED".equals(alert.getStatus())) {
            alert.setStatus("RESOLVED");
            alert.setResolvedAt(LocalDateTime.now());
            alert.setResolvedBy(resolvedBy);
            alert.setResolutionNote(note);
            alertMapper.updateById(alert);
            log.info("告警已解决 - AlertID: {}, 解决人: {}, 备注: {}", alertId, resolvedBy, note);
        }
    }

    /**
     * 忽略告警
     */
    public void ignoreAlert(String alertId) {
        SystemAlert alert = alertMapper.selectById(alertId);
        if (alert != null) {
            alert.setStatus("IGNORED");
            alertMapper.updateById(alert);
            log.info("告警已忽略 - AlertID: {}", alertId);
        }
    }

    /**
     * 获取未解决的告警列表
     */
    public List<SystemAlert> getUnresolvedAlerts() {
        LambdaQueryWrapper<SystemAlert> wrapper = new LambdaQueryWrapper<>();
        wrapper.in(SystemAlert::getStatus, "TRIGGERED", "ACKNOWLEDGED");
        wrapper.orderByDesc(SystemAlert::getTriggeredAt);
        return alertMapper.selectList(wrapper);
    }

    /**
     * 获取商户的告警列表
     */
    public List<SystemAlert> getMerchantAlerts(String merchantId, boolean includeResolved) {
        LambdaQueryWrapper<SystemAlert> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(SystemAlert::getMerchantId, merchantId);
        if (!includeResolved) {
            wrapper.in(SystemAlert::getStatus, "TRIGGERED", "ACKNOWLEDGED");
        }
        wrapper.orderByDesc(SystemAlert::getTriggeredAt);
        return alertMapper.selectList(wrapper);
    }

    /**
     * 获取告警统计
     */
    public Map<String, Long> getAlertStats() {
        List<SystemAlert> alerts = alertMapper.selectList(null);
        long total = alerts.size();
        long triggered = 0;
        long acknowledged = 0;
        long resolved = 0;

        for (SystemAlert alert : alerts) {
            String status = alert.getStatus();
            if ("TRIGGERED".equals(status)) {
                triggered++;
            } else if ("ACKNOWLEDGED".equals(status)) {
                acknowledged++;
            } else if ("RESOLVED".equals(status)) {
                resolved++;
            }
        }

        Map<String, Long> stats = new HashMap<>();
        stats.put("total", total);
        stats.put("triggered", triggered);
        stats.put("acknowledged", acknowledged);
        stats.put("resolved", resolved);
        return stats;
    }

    /**
     * 检查是否存在未解决的告警
     */
    private boolean hasUnresolvedAlert(String targetId, String alertType) {
        LambdaQueryWrapper<SystemAlert> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(SystemAlert::getAlertType, alertType);
        wrapper.in(SystemAlert::getStatus, "TRIGGERED", "ACKNOWLEDGED");
        if (targetId != null) {
            wrapper.eq(SystemAlert::getAgentId, targetId);
        }
        return alertMapper.selectCount(wrapper) > 0;
    }

    /**
     * 发送告警通知
     */
    private void sendAlertNotification(SystemAlert alert) {
        String message = String.format("[%s][%s] %s - %s",
                alert.getSeverity(), alert.getAlertName(), alert.getMessage(), alert.getAlertCode());

        if ("CRITICAL".equals(alert.getSeverity())) {
            log.error("【严重告警】{}", message);
        } else if ("HIGH".equals(alert.getSeverity())) {
            log.warn("【高危告警】{}", message);
        } else if ("MEDIUM".equals(alert.getSeverity())) {
            log.warn("【中危告警】{}", message);
        } else {
            log.info("【低危告警】{}", message);
        }
    }

    /**
     * 定时清理过期告警
     */
    @Scheduled(cron = "0 0 3 * * ?")
    public void cleanupOldAlerts() {
        try {
            LocalDateTime threshold = LocalDateTime.now().minusDays(30);
            LambdaQueryWrapper<SystemAlert> wrapper = new LambdaQueryWrapper<>();
            wrapper.le(SystemAlert::getResolvedAt, threshold);
            wrapper.eq(SystemAlert::getStatus, "RESOLVED");

            int deleted = alertMapper.delete(wrapper);
            if (deleted > 0) {
                log.info("已清理{}条过期告警记录", deleted);
            }
        } catch (Exception e) {
            log.error("清理过期告警失败", e);
        }
    }

    /**
     * 定时检查Agent离线状态
     */
    @Scheduled(fixedRate = 60000)
    public void checkAgentOfflineStatus() {
        log.debug("检查Agent离线状态");
    }
}
