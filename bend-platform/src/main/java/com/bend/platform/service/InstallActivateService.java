package com.bend.platform.service;

import com.bend.platform.dto.InstallActivateRequest;
import com.bend.platform.dto.InstallActivateResponse;
import com.bend.platform.dto.LicenseCreateRequest;
import com.bend.platform.dto.LicenseIssueResponse;
import com.bend.platform.dto.PermissionCreateRequest;
import com.bend.platform.entity.MerchantPermission;
import com.bend.platform.config.MasterModeCondition;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.service.impl.MerchantDataExportService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Conditional;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 分控安装激活服务（总控侧）
 *
 * <p>安装器调用激活接口时，编排四步原子操作:
 * <ol>
 *   <li>校验并消费激活码 → 获取 merchantId</li>
 *   <li>签发 License（软件授权凭证，终身有效）</li>
 *   <li>创建 Permission（使用权限，默认1年有效）</li>
 *   <li>导出商户数据 → 生成 INSERT IGNORE SQL</li>
 * </ol>
 *
 * <p>四步在同一事务中完成，任意一步失败则全部回滚。
 */
@Slf4j
@Service
@RequiredArgsConstructor
@Conditional(MasterModeCondition.class)
public class InstallActivateService {

    private final MerchantRegistrationCodeService registrationCodeService;
    private final LicenseService licenseService;
    private final PermissionService permissionService;
    private final MerchantDataExportService dataExportService;

    @Value("${tenant.db-password:D$U@GAMECeKfidb}")
    private String tenantDbPassword;

    /**
     * 执行安装激活。
     */
    @Transactional(rollbackFor = Exception.class)
    public InstallActivateResponse activate(InstallActivateRequest request, String masterUrl) {
        // 1. 校验并消费激活码
        MerchantRegistrationCodeService.ActivationResult codeResult =
                registrationCodeService.validateAndConsume(request.getActivationCode());
        if (!codeResult.isSuccess()) {
            throw new BusinessException(ResultCode.RegistrationCode.INVALID,
                    codeResult.getMessage());
        }
        String merchantId = codeResult.getMerchantId();
        log.info("[安装激活] 激活码校验通过 merchantId={}", merchantId);

        // 2. 签发 License（软件授权凭证，无到期时间）
        LicenseCreateRequest licenseReq = new LicenseCreateRequest();
        licenseReq.setMerchantId(merchantId);
        licenseReq.setMachineFingerprint(request.getMachineFingerprint());
        LicenseIssueResponse licenseResp = licenseService.issueLicense(licenseReq);

        log.info("[安装激活] License签发成功 licenseKey={} merchantId={}",
                licenseResp.getLicenseKey(), merchantId);

        // 3. 创建使用权限（默认1年有效）
        java.time.LocalDateTime expireAt = java.time.LocalDateTime.now().plusYears(1);
        PermissionCreateRequest permReq = new PermissionCreateRequest();
        permReq.setMerchantId(merchantId);
        permReq.setExpireAt(expireAt);
        permReq.setMaxAgents(5);
        permReq.setMaxTasks(50);
        MerchantPermission perm = permissionService.createOrRenew(permReq);
        log.info("[安装激活] 使用权限创建成功 merchantId={} expireAt={}", merchantId, expireAt);

        // 4. 导出商户数据
        String merchantData = dataExportService.export(merchantId);

        // 5. 组装响应
        InstallActivateResponse resp = new InstallActivateResponse();
        resp.setLicenseKey(licenseResp.getLicenseKey());
        resp.setLicenseSecret(licenseResp.getLicenseSecret());
        resp.setMerchantId(merchantId);
        resp.setMerchantName(licenseResp.getMerchantName());
        resp.setMasterUrl(masterUrl);
        resp.setMerchantData(merchantData);
        resp.setDbPassword(tenantDbPassword);
        resp.setExpireAt(perm.getExpireAt().toString());
        resp.setMaxAgents(perm.getMaxAgents());
        resp.setMaxTasks(perm.getMaxTasks());
        return resp;
    }
}
