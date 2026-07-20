package com.bend.platform.service;

import com.bend.platform.dto.LicenseVerifyRequest;
import com.bend.platform.dto.LicenseVerifyResponse;
import com.bend.platform.entity.LicenseVerifyCache;

/**
 * 分控侧 License 客户端服务
 *
 * <p>仅分控(mode=tenant)启用。职责:
 * <ul>
 *   <li>向总控发起校验(verify),验签后写入本地缓存</li>
 *   <li>总控不可达时,读本地签名缓存按离线宽限判活</li>
 *   <li>对外暴露 isAuthorized() 供拦截器/业务判断当前是否仍有权限</li>
 * </ul>
 */
public interface LicenseClientService {

    /**
     * 向总控发起一次校验,刷新本地缓存。
     * @return true=校验有效(或离线宽限内仍可用) false=已失效
     */
    boolean verifyNow();

    /**
     * 当前是否仍有授权(有效 或 离线宽限内)。
     * 供 LicenseGateFilter 和业务层调用。
     */
    boolean isAuthorized();

    /**
     * 当前授权状态详情(供后台/日志展示)。
     */
    LicenseStatus getStatus();

    /**
     * 取最近一次缓存的校验结果(可空)。
     */
    LicenseVerifyCache getCache();

    record LicenseStatus(
            boolean authorized,
            String source,            // ONLINE / OFFLINE_GRACE / NONE
            boolean lastVerifySuccess,
            String invalidReason,
            java.time.LocalDateTime expireAt,
            java.time.LocalDateTime lastVerifiedAt,
            java.time.LocalDateTime offlineDeadline
    ) {}
}
