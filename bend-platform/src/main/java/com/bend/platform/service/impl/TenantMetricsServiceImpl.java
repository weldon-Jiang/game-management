package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bend.platform.dto.TenantMetricsReport;
import com.bend.platform.dto.TenantStatusVo;
import com.bend.platform.entity.Merchant;
import com.bend.platform.entity.MerchantLicense;
import com.bend.platform.entity.TenantMetrics;
import com.bend.platform.repository.MerchantLicenseMapper;
import com.bend.platform.repository.TenantMetricsMapper;
import com.bend.platform.service.MerchantService;
import com.bend.platform.service.TenantMetricsService;
import com.bend.platform.util.LicenseSignUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class TenantMetricsServiceImpl implements TenantMetricsService {

    private final TenantMetricsMapper metricsMapper;
    private final MerchantLicenseMapper licenseMapper;
    private final LicenseSignUtil signUtil;
    private final MerchantService merchantService;

    @Value("${license.online-threshold-minutes:15}")
    private int onlineThresholdMinutes;

    @Override
    public boolean report(TenantMetricsReport report) {
        // 用 licenseKey + secret 鉴权
        MerchantLicense license = licenseMapper.selectByLicenseKey(report.getLicenseKey());
        if (license == null || !signUtil.verifySecret(report.getLicenseSecret(), license.getLicenseSecret())) {
            log.warn("分控指标上报鉴权失败 licenseKey={}", report.getLicenseKey());
            return false;
        }
        TenantMetrics m = new TenantMetrics();
        m.setMerchantId(license.getMerchantId());
        m.setLicenseKey(report.getLicenseKey());
        m.setReportAt(report.getReportAt());
        m.setOnlineAgentCount(report.getOnlineAgentCount());
        m.setTotalAgentCount(report.getTotalAgentCount());
        m.setTodayTaskCount(report.getTodayTaskCount());
        m.setRunningTaskCount(report.getRunningTaskCount());
        m.setTodayPointsConsumed(report.getTodayPointsConsumed());
        m.setBalance(report.getBalance());
        m.setLicenseStatus(report.getLicenseStatus());
        m.setPlatformVersion(report.getPlatformVersion());
        m.setExtra(report.getExtra());
        metricsMapper.insert(m);
        log.info("接收分控指标上报 merchantId={} onlineAgents={} todayTasks={}",
                license.getMerchantId(), report.getOnlineAgentCount(), report.getTodayTaskCount());
        return true;
    }

    @Override
    public List<TenantMetrics> recentByMerchant(String merchantId, int limit) {
        return metricsMapper.selectRecentByMerchant(merchantId, limit);
    }

    @Override
    public List<TenantMetrics> latestPerMerchant() {
        return metricsMapper.selectLatestPerMerchant();
    }

    @Override
    public List<TenantStatusVo> listStatus() {
        // 1. 所有 active license(每商户一条)
        List<MerchantLicense> licenses = licenseMapper.selectList(
                new LambdaQueryWrapper<MerchantLicense>()
                        .eq(MerchantLicense::getStatus, "active")
                        .isNotNull(MerchantLicense::getMerchantId));
        // 一个商户可能有多条 license,保留最新
        Map<String, MerchantLicense> licenseByMerchant = new HashMap<>();
        for (MerchantLicense l : licenses) {
            MerchantLicense exist = licenseByMerchant.get(l.getMerchantId());
            if (exist == null || (l.getCreatedTime() != null && exist.getCreatedTime() != null
                    && l.getCreatedTime().isAfter(exist.getCreatedTime()))) {
                licenseByMerchant.put(l.getMerchantId(), l);
            }
        }

        // 2. 每商户最新指标
        List<TenantMetrics> latest = metricsMapper.selectLatestPerMerchant();
        Map<String, TenantMetrics> metricsByMerchant = latest.stream()
                .collect(Collectors.toMap(TenantMetrics::getMerchantId, m -> m, (a, b) -> a));

        // 3. 商户名(批量)
        Collection<String> merchantIds = new ArrayList<>(licenseByMerchant.keySet());
        Map<String, String> nameMap = new HashMap<>();
        if (!merchantIds.isEmpty()) {
            List<Merchant> merchants = merchantService.findByIds(merchantIds);
            if (merchants != null) {
                for (Merchant m : merchants) {
                    nameMap.put(m.getId(), m.getName());
                }
            }
        }

        LocalDateTime now = LocalDateTime.now();
        List<TenantStatusVo> result = new ArrayList<>();
        for (Map.Entry<String, MerchantLicense> e : licenseByMerchant.entrySet()) {
            String mid = e.getKey();
            MerchantLicense lic = e.getValue();
            TenantMetrics m = metricsByMerchant.get(mid);

            // 最近活动时间 = max(license校验时间, 指标接收时间)
            LocalDateTime lastSeen = lic.getLastVerifiedAt();
            String source = "LICENSE_VERIFY";
            if (m != null && m.getReceivedAt() != null) {
                if (lastSeen == null || m.getReceivedAt().isAfter(lastSeen)) {
                    lastSeen = m.getReceivedAt();
                    source = "METRICS_REPORT";
                }
            }

            TenantStatusVo vo = new TenantStatusVo();
            vo.setMerchantId(mid);
            vo.setMerchantName(nameMap.get(mid));
            vo.setLicenseStatus(lic.getStatus());
            vo.setLicenseExpireAt(lic.getExpireAt());
            if (m != null) {
                vo.setOnlineAgents(m.getOnlineAgentCount());
                vo.setTodayTasks(m.getTodayTaskCount());
            }
            if (lastSeen != null) {
                vo.setLastSeenAt(lastSeen);
                vo.setLastSeenSource(source);
                long minutes = Duration.between(lastSeen, now).toMinutes();
                vo.setOnline(minutes >= 0 && minutes <= onlineThresholdMinutes);
            } else {
                vo.setLastSeenSource("NONE");
                vo.setOnline(false);
            }
            result.add(vo);
        }
        return result;
    }
}
