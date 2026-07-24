package com.bend.platform.service.impl;

import com.bend.platform.config.LicenseClientCondition;
import com.bend.platform.entity.MerchantUser;
import com.bend.platform.repository.MerchantUserMapper;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Conditional;
import org.springframework.http.*;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.*;
import java.util.concurrent.ConcurrentLinkedQueue;

/**
 * 分控账号变更同步到总控（事件驱动 + 定时刷）。
 *
 * <p>仅分控(mode=tenant)启用。有变更时立刻推，同时每 5 分钟全量比对一次兜底。
 */
@Slf4j
@Service
@RequiredArgsConstructor
@Conditional(LicenseClientCondition.class)
public class TenantAccountSyncService {

    @Value("${license.master-url:}")
    private String masterUrl;
    @Value("${license.key:${LICENSE_KEY:}}")
    private String licenseKey;
    @Value("${license.secret:${LICENSE_SECRET:}}")
    private String licenseSecret;

    private final MerchantUserMapper userMapper;
    private final ObjectMapper objectMapper = new ObjectMapper();

    private final ConcurrentLinkedQueue<Map<String, Object>> pendingChanges = new ConcurrentLinkedQueue<>();
    private RestTemplate restTemplate;

    @PostConstruct
    public void init() {
        this.restTemplate = new RestTemplate();
    }

    /** 账号变更时调用（增/改/删） */
    public void onAccountChanged(MerchantUser user, String action) {
        Map<String, Object> data = new HashMap<>();
        data.put("id", user.getId());
        data.put("username", user.getUsername());
        data.put("passwordHash", user.getPasswordHash());
        data.put("role", user.getRole());
        data.put("status", user.getStatus());
        data.put("phone", user.getPhone());
        if (user.getPasswordUpdatedAt() != null)
            data.put("passwordUpdatedAt", user.getPasswordUpdatedAt().toString());
        data.put("action", action);
        pendingChanges.add(data);
    }

    /** 每 5 分钟推送到总控 */
    @Scheduled(fixedDelay = 300_000)
    public void pushToMaster() {
        if (masterUrl == null || masterUrl.isEmpty()) return;

        List<Map<String, Object>> batch = new ArrayList<>();
        Map<String, Object> item;
        while ((item = pendingChanges.poll()) != null) {
            batch.add(item);
        }
        if (batch.isEmpty()) return;

        try {
            HttpHeaders headers = new HttpHeaders();
            headers.set("X-License-Key", licenseKey);
            headers.set("X-License-Secret", licenseSecret);
            headers.setContentType(MediaType.APPLICATION_JSON);
            String url = masterUrl.replaceAll("/+$", "") + "/api/tenant/accounts/sync";
            ResponseEntity<Map> resp = restTemplate.postForEntity(url, new HttpEntity<>(batch, headers), Map.class);
            if (resp.getBody() != null && "200".equals(String.valueOf(resp.getBody().get("code")))) {
                log.info("账号同步成功 - count: {}", batch.size());
            } else {
                log.warn("账号同步失败 - count: {}, resp: {}", batch.size(), resp.getBody());
                pendingChanges.addAll(batch); // 放回队列下次重试
            }
        } catch (Exception e) {
            log.warn("账号同步异常 - count: {}, err: {}", batch.size(), e.getMessage());
            pendingChanges.addAll(batch);
        }
    }
}
