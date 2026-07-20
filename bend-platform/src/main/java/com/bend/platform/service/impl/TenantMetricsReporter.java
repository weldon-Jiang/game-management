package com.bend.platform.service.impl;

import com.bend.platform.config.LicenseClientCondition;
import com.bend.platform.dto.TenantMetricsReport;
import com.bend.platform.entity.AgentInstance;
import com.bend.platform.entity.LicenseVerifyCache;
import com.bend.platform.repository.AgentInstanceMapper;
import com.bend.platform.repository.LicenseVerifyCacheMapper;
import com.bend.platform.service.LicenseClientService;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Conditional;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 分控汇总指标采集 + 上报(仅 tenant 模式)
 *
 * <p>采集本地库的 Agent 在线数、今日任务数、余额等,POST 到总控 /api/tenant-metrics/report。
 */
@Slf4j
@Component
@RequiredArgsConstructor
@Conditional(LicenseClientCondition.class)
public class TenantMetricsReporter {

    @Value("${license.master-url:}")
    private String masterUrl;

    @Value("${license.key:${LICENSE_KEY:}}")
    private String licenseKey;

    @Value("${license.secret:${LICENSE_SECRET:}}")
    private String licenseSecret;

    @Value("${license.metrics-interval-ms:300000}")
    private long intervalMs;

    private final AgentInstanceMapper agentInstanceMapper;
    private final LicenseVerifyCacheMapper verifyCacheMapper;
    private final LicenseClientService licenseClientService;
    private final ObjectMapper objectMapper;
    private final JdbcTemplate jdbcTemplate;

    /**
     * 采集并上报一次。由 TenantMetricsScheduler 定时调用,也可手动触发。
     */
    public void reportOnce() {
        if (masterUrl == null || masterUrl.isEmpty() || licenseKey == null || licenseKey.isEmpty()) {
            return;
        }
        try {
            TenantMetricsReport report = collect();
            report.setLicenseKey(licenseKey);
            report.setLicenseSecret(licenseSecret);
            report.setReportAt(LocalDateTime.now());

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            HttpEntity<TenantMetricsReport> entity = new HttpEntity<>(report, headers);
            String url = masterUrl.replaceAll("/+$", "") + "/api/tenant-metrics/report";
            ResponseEntity<String> resp = new org.springframework.web.client.RestTemplate()
                    .postForEntity(url, entity, String.class);
            log.info("分控指标已上报 status={}", resp.getStatusCode().value());
        } catch (Exception e) {
            log.warn("分控指标上报失败: {}", e.getMessage());
        }
    }

    private TenantMetricsReport collect() {
        TenantMetricsReport r = new TenantMetricsReport();
        try {
            // Agent 在线/总数
            List<AgentInstance> agents = agentInstanceMapper.selectList(null);
            int total = agents == null ? 0 : agents.size();
            int online = 0;
            if (agents != null) {
                for (AgentInstance a : agents) {
                    if ("online".equalsIgnoreCase(a.getStatus())) online++;
                }
            }
            r.setTotalAgentCount(total);
            r.setOnlineAgentCount(online);
        } catch (Exception e) {
            log.debug("采集Agent数失败: {}", e.getMessage());
        }

        // license 状态
        try {
            LicenseClientService.LicenseStatus st = licenseClientService.getStatus();
            r.setLicenseStatus(st.source());
        } catch (Exception ignored) {
        }

        // 业务指标:通过 merchantId(来自 license 校验缓存)查本地库
        try {
            LicenseVerifyCache cache = verifyCacheMapper.selectByLicenseKey(licenseKey);
            if (cache != null && cache.getMerchantId() != null) {
                String mid = cache.getMerchantId();
                Integer todayTasks = queryInt(
                        "SELECT COUNT(*) FROM task WHERE merchant_id=? AND DATE(created_time)=CURDATE()", mid);
                Integer runningTasks = queryInt(
                        "SELECT COUNT(*) FROM task WHERE merchant_id=? AND status='running'", mid);
                Integer todayPoints = queryInt(
                        "SELECT COALESCE(SUM(points_deducted),0) FROM automation_billing_event WHERE merchant_id=? AND DATE(created_time)=CURDATE()", mid);
                Integer balance = queryInt(
                        "SELECT COALESCE(balance,0) FROM merchant_balance WHERE merchant_id=?", mid);
                r.setTodayTaskCount(todayTasks);
                r.setRunningTaskCount(runningTasks);
                r.setTodayPointsConsumed(todayPoints);
                r.setBalance(balance);
            }
        } catch (Exception e) {
            log.debug("采集业务指标失败: {}", e.getMessage());
        }

        r.setPlatformVersion("tenant-1.0.0");
        return r;
    }

    private Integer queryInt(String sql, String merchantId) {
        try {
            Integer v = jdbcTemplate.queryForObject(sql, Integer.class, merchantId);
            return v == null ? 0 : v;
        } catch (Exception e) {
            return 0;
        }
    }
}
