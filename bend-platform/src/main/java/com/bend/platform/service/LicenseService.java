package com.bend.platform.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.LicenseCreateRequest;
import com.bend.platform.dto.LicenseIssueResponse;
import com.bend.platform.dto.LicenseVerifyRequest;
import com.bend.platform.dto.LicenseVerifyResponse;
import com.bend.platform.entity.MerchantLicense;

import java.util.List;

/**
 * 商户授权(License)服务
 *
 * <p>总控侧: 签发 / 查询 / 吊销 / 校验分控上报。
 * 分控侧: 见 {@link com.bend.platform.service.LicenseClientService}(向总控校验 + 本地缓存)。
 */
public interface LicenseService {

    /**
     * 为商户签发一个新的 license(打包分控包前调用)。
     * 返回的 licenseSecret 明文仅此一次返回。
     */
    LicenseIssueResponse issueLicense(LicenseCreateRequest request);

    /**
     * 处理分控的校验请求(分控启动 + 每30分钟调用)。
     * 校验通过则返回带签名的结果,分控缓存用于离线宽限。
     */
    LicenseVerifyResponse verify(LicenseVerifyRequest request, String clientIp);

    /**
     * 吊销 license。
     */
    void revoke(String licenseId, String reason);

    // renew() 已迁移到 PermissionService（License 不负责到期管理）

    /**
     * 查询商户的所有 license。
     */
    List<MerchantLicense> listByMerchant(String merchantId);

    /**
     * 分页查询 license(总控后台用)。
     */
    IPage<MerchantLicense> page(int pageNum, int pageSize, String merchantId, String status);

    /**
     * 根据ID查询。
     */
    MerchantLicense findById(String id);
}
