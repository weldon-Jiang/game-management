package com.bend.platform.controller;

import com.bend.platform.config.MasterModeCondition;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.MerchantLicense;
import com.bend.platform.entity.MerchantUser;
import com.bend.platform.repository.MerchantLicenseMapper;
import com.bend.platform.repository.MerchantUserMapper;
import com.bend.platform.util.LicenseSignUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Conditional;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 分控账号同步回总控（增/改/删）。
 *
 * <p>分控创建、修改、删除账号后定时推送，总控 upsert。
 */
@Slf4j
@RestController
@RequestMapping("/api/tenant")
@RequiredArgsConstructor
@Conditional(MasterModeCondition.class)
public class TenantAccountSyncController {

    private final MerchantUserMapper userMapper;
    private final MerchantLicenseMapper licenseMapper;
    private final LicenseSignUtil signUtil;

    @PostMapping("/accounts/sync")
    public ApiResponse<Void> syncAccounts(
            @RequestHeader("X-License-Key") String licenseKey,
            @RequestHeader("X-License-Secret") String licenseSecret,
            @RequestBody List<Map<String, Object>> accounts) {

        MerchantLicense lic = licenseMapper.selectByLicenseKey(licenseKey);
        if (lic == null) return ApiResponse.error(404, "License 不存在");
        if (!signUtil.verifySecret(licenseSecret, lic.getLicenseSecret()))
            return ApiResponse.error(403, "License 密钥错误");

        String merchantId = lic.getMerchantId();

        for (Map<String, Object> acct : accounts) {
            String id = (String) acct.get("id");
            String action = (String) acct.getOrDefault("action", "upsert");

            if ("delete".equals(action)) {
                userMapper.deleteById(id);
                log.info("账号同步-删除: {}", id);
                continue;
            }

            MerchantUser existing = userMapper.selectById(id);
            if (existing != null) {
                existing.setUsername((String) acct.get("username"));
                existing.setPasswordHash((String) acct.get("passwordHash"));
                existing.setRole((String) acct.get("role"));
                existing.setStatus((String) acct.get("status"));
                existing.setPhone((String) acct.get("phone"));
                Object pwdAt = acct.get("passwordUpdatedAt");
                if (pwdAt != null) existing.setPasswordUpdatedAt(java.time.LocalDateTime.parse(pwdAt.toString().replace("T", " ").substring(0, 19), java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));
                userMapper.updateById(existing);
            } else {
                MerchantUser u = new MerchantUser();
                u.setId(id);
                u.setMerchantId(merchantId);
                u.setUsername((String) acct.get("username"));
                u.setPasswordHash((String) acct.get("passwordHash"));
                u.setRole((String) acct.get("role"));
                u.setStatus((String) acct.get("status"));
                u.setPhone((String) acct.getOrDefault("phone", ""));
                u.setCreatedTime(java.time.LocalDateTime.now());
                Object pwdAt = acct.get("passwordUpdatedAt");
                if (pwdAt != null) u.setPasswordUpdatedAt(java.time.LocalDateTime.parse(pwdAt.toString().replace("T", " ").substring(0, 19), java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));
                userMapper.insert(u);
            }
        }

        log.info("账号同步完成 - merchant: {}, count: {}", merchantId, accounts.size());
        return ApiResponse.success(null);
    }
}
