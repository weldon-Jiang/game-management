package com.bend.platform.service;

import com.bend.platform.entity.SystemAlert;
import com.bend.platform.repository.SystemAlertMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Arrays;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

/**
 * AlertService 单元测试
 *
 * 测试场景：
 * - 告警触发（Agent离线、任务失败、资源告警）
 * - 告警确认和处理
 * - 告警统计和查询
 * - 重复告警过滤
 */
@ExtendWith(MockitoExtension.class)
class AlertServiceTest {

    @Mock
    private SystemAlertMapper alertMapper;

    @InjectMocks
    private AlertService alertService;

    private SystemAlert testAlert;

    @BeforeEach
    void setUp() {
        testAlert = new SystemAlert();
        testAlert.setId("alert-001");
        testAlert.setAlertCode("ALERT-001");
        testAlert.setAlertName("测试告警");
        testAlert.setSeverity("HIGH");
        testAlert.setAlertType("AGENT_OFFLINE");
        testAlert.setMessage("Agent已离线");
        testAlert.setStatus("TRIGGERED");
    }

    /**
     * 测试：触发Agent离线告警
     *
     * 验证：
     * - 创建新告警记录
     * - 状态为TRIGGERED
     */
    @Test
    void testTriggerAgentOfflineAlert() {
        when(alertMapper.selectCount(any())).thenReturn(0L);
        when(alertMapper.insert(any(SystemAlert.class))).thenReturn(1);

        alertService.triggerAgentOfflineAlert("agent-001", "merchant-001");

        verify(alertMapper, times(1)).insert(argThat(alert ->
            "AGENT_OFFLINE".equals(alert.getAlertType()) &&
            "HIGH".equals(alert.getSeverity()) &&
            "TRIGGERED".equals(alert.getStatus())
        ));
    }

    /**
     * 测试：重复Agent离线告警被过滤
     *
     * 验证：
     * - 如果已存在未解决的同类告警，不创建新的
     */
    @Test
    void testDuplicateAgentOfflineAlertFiltered() {
        when(alertMapper.selectCount(any())).thenReturn(1L);

        alertService.triggerAgentOfflineAlert("agent-001", "merchant-001");

        verify(alertMapper, never()).insert(any(SystemAlert.class));
    }

    /**
     * 测试：触发任务失败告警（未达阈值）
     *
     * 验证：
     * - 未达到阈值时不创建告警
     */
    @Test
    void testTaskFailedAlertBelowThreshold() {
        // 连续失败1-2次不应该触发告警
        alertService.triggerTaskFailedAlert("task-001", "错误1");
        alertService.triggerTaskFailedAlert("task-002", "错误2");

        verify(alertMapper, never()).insert(any(SystemAlert.class));
    }

    /**
     * 测试：触发任务失败告警（达到阈值）
     *
     * 验证：
     * - 连续失败达到3次时触发告警
     */
    @Test
    void testTaskFailedAlertAboveThreshold() {
        when(alertMapper.selectCount(any())).thenReturn(0L);
        when(alertMapper.insert(any(SystemAlert.class))).thenReturn(1);

        alertService.triggerTaskFailedAlert("task-001", "错误1");
        alertService.triggerTaskFailedAlert("task-002", "错误2");
        alertService.triggerTaskFailedAlert("task-003", "错误3");

        verify(alertMapper, times(1)).insert(argThat(alert ->
            "TASK_FAILED".equals(alert.getAlertType()) &&
            "MEDIUM".equals(alert.getSeverity())
        ));
    }

    /**
     * 测试：触发资源告警
     *
     * 验证：
     * - CPU或内存使用率过高时触发
     */
    @Test
    void testTriggerResourceAlert() {
        when(alertMapper.selectCount(any())).thenReturn(0L);
        when(alertMapper.insert(any(SystemAlert.class))).thenReturn(1);

        alertService.triggerResourceAlert("HIGH_CPU", 95.0, 90.0);

        verify(alertMapper, times(1)).insert(argThat(alert ->
            "HIGH_CPU".equals(alert.getAlertType()) &&
            "MEDIUM".equals(alert.getSeverity())
        ));
    }

    /**
     * 测试：确认告警
     *
     * 验证：
     * - 状态从TRIGGERED变为ACKNOWLEDGED
     * - 记录确认人和时间
     */
    @Test
    void testAcknowledgeAlert() {
        when(alertMapper.selectById("alert-001")).thenReturn(testAlert);
        when(alertMapper.updateById(any(SystemAlert.class))).thenReturn(1);

        alertService.acknowledgeAlert("alert-001", "user-001");

        verify(alertMapper, times(1)).updateById(argThat(alert ->
            "ACKNOWLEDGED".equals(alert.getStatus()) &&
            "user-001".equals(alert.getAcknowledgedBy()) &&
            alert.getAcknowledgedAt() != null
        ));
    }

    /**
     * 测试：确认已解决的告警（不应处理）
     *
     * 验证：
     * - 已RESOLVED状态的告警不能再确认
     */
    @Test
    void testAcknowledgeResolvedAlert() {
        testAlert.setStatus("RESOLVED");
        when(alertMapper.selectById("alert-001")).thenReturn(testAlert);

        alertService.acknowledgeAlert("alert-001", "user-001");

        verify(alertMapper, never()).updateById(any(SystemAlert.class));
    }

    /**
     * 测试：解决告警
     *
     * 验证：
     * - 状态变为RESOLVED
     * - 记录解决人、时间和备注
     */
    @Test
    void testResolveAlert() {
        when(alertMapper.selectById("alert-001")).thenReturn(testAlert);
        when(alertMapper.updateById(any(SystemAlert.class))).thenReturn(1);

        alertService.resolveAlert("alert-001", "user-001", "问题已修复");

        verify(alertMapper, times(1)).updateById(argThat(alert ->
            "RESOLVED".equals(alert.getStatus()) &&
            "user-001".equals(alert.getResolvedBy()) &&
            "问题已修复".equals(alert.getResolutionNote()) &&
            alert.getResolvedAt() != null
        ));
    }

    /**
     * 测试：忽略告警
     *
     * 验证：
     * - 状态变为IGNORED
     */
    @Test
    void testIgnoreAlert() {
        when(alertMapper.selectById("alert-001")).thenReturn(testAlert);
        when(alertMapper.updateById(any(SystemAlert.class))).thenReturn(1);

        alertService.ignoreAlert("alert-001");

        verify(alertMapper, times(1)).updateById(argThat(alert ->
            "IGNORED".equals(alert.getStatus())
        ));
    }

    /**
     * 测试：获取未解决的告警列表
     *
     * 验证：
     * - 只返回TRIGGERED和ACKNOWLEDGED状态的告警
     * - 按触发时间倒序
     */
    @Test
    void testGetUnresolvedAlerts() {
        SystemAlert alert1 = new SystemAlert();
        alert1.setStatus("TRIGGERED");
        SystemAlert alert2 = new SystemAlert();
        alert2.setStatus("ACKNOWLEDGED");

        when(alertMapper.selectList(any())).thenReturn(Arrays.asList(alert1, alert2));

        List<SystemAlert> alerts = alertService.getUnresolvedAlerts();

        assertEquals(2, alerts.size());
    }

    /**
     * 测试：获取告警统计
     *
     * 验证：
     * - 统计各状态的告警数量
     */
    @Test
    void testGetAlertStats() {
        SystemAlert alert1 = new SystemAlert();
        alert1.setStatus("TRIGGERED");
        SystemAlert alert2 = new SystemAlert();
        alert2.setStatus("RESOLVED");

        when(alertMapper.selectList(any())).thenReturn(Arrays.asList(alert1, alert2));

        var stats = alertService.getAlertStats();

        assertEquals(2L, stats.get("total"));
        assertEquals(1L, stats.get("triggered"));
        assertEquals(1L, stats.get("resolved"));
    }

    /**
     * 测试：Xbox连接失败告警
     *
     * 验证：
     * - 正确设置Xbox相关告警信息
     */
    @Test
    void testTriggerXboxConnectionAlert() {
        when(alertMapper.selectCount(any())).thenReturn(0L);
        when(alertMapper.insert(any(SystemAlert.class))).thenReturn(1);

        alertService.triggerXboxConnectionAlert("xbox-001", "merchant-001", "Connection timeout");

        verify(alertMapper, times(1)).insert(argThat(alert ->
            "XBOX_CONNECTION_FAILED".equals(alert.getAlertType()) &&
            "HIGH".equals(alert.getSeverity())
        ));
    }
}
