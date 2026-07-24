package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.dto.LicenseCreateRequest;
import com.bend.platform.dto.LicenseIssueResponse;
import com.bend.platform.dto.LicenseVerifyRequest;
import com.bend.platform.dto.LicenseVerifyResponse;
import com.bend.platform.entity.MerchantLicense;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.service.LicenseService;
import com.bend.platform.util.UserContext;
import com.bend.platform.config.MasterModeCondition;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Conditional;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * License(商户授权)Controller — 仅管理软件授权凭证(签发/吊销/查询)。
 * 使用权限(到期/续期/配额)请用 {@link com.bend.platform.controller.PermissionController}。
 *
 * <p>总控后台管理接口(需 platform_admin): 签发 / 查询 / 吊销 / 续期。
 * <p>分控校验接口(公开,不走 JWT): POST /api/licenses/verify。
 */
@RestController
@RequestMapping("/api/licenses")
@RequiredArgsConstructor
@Conditional(MasterModeCondition.class)
public class LicenseController {

    private final LicenseService licenseService;

    /**
     * 签发 license(打包分控包前调用)。仅平台管理员。
     * expireAt/maxAgents/maxTasks/features 已迁移到 Permission，此处不再接收。
     */
    @PostMapping
    public ApiResponse<LicenseIssueResponse> issue(@RequestBody LicenseCreateRequest request) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        if (request.getMerchantId() == null) {
            throw new BusinessException(ResultCode.System.BAD_REQUEST);
        }
        return ApiResponse.success("授权签发成功", licenseService.issueLicense(request));
    }

    /**
     * 分控校验 license(公开接口,分控启动 + 每30分钟调用)。
     * 该接口需在 WebMvcConfig 中排除 JWT 拦截。
     */
    @PostMapping("/verify")
    public ApiResponse<LicenseVerifyResponse> verify(@RequestBody LicenseVerifyRequest request,
                                                     HttpServletRequest httpRequest) {
        if (request.getLicenseKey() == null || request.getLicenseSecret() == null) {
            throw new BusinessException(ResultCode.System.BAD_REQUEST);
        }
        String clientIp = extractClientIp(httpRequest);
        return ApiResponse.success(licenseService.verify(request, clientIp));
    }

    /**
     * 查询商户的所有 license。仅平台管理员。
     */
    @GetMapping("/merchant/{merchantId}")
    public ApiResponse<List<MerchantLicense>> listByMerchant(@PathVariable String merchantId) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        return ApiResponse.success(licenseService.listByMerchant(merchantId));
    }

    /**
     * 分页查询 license。仅平台管理员。
     */
    @GetMapping
    public ApiResponse<IPage<MerchantLicense>> page(@RequestParam(defaultValue = "1") int pageNum,
                                                    @RequestParam(defaultValue = "20") int pageSize,
                                                    @RequestParam(required = false) String merchantId,
                                                    @RequestParam(required = false) String status) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        return ApiResponse.success(licenseService.page(pageNum, pageSize, merchantId, status));
    }

    /**
     * 吊销 license。仅平台管理员。
     */
    @PutMapping("/{id}/revoke")
    public ApiResponse<Void> revoke(@PathVariable String id,
                                    @RequestParam(required = false) String reason) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        licenseService.revoke(id, reason);
        return ApiResponse.success("吊销成功", null);
    }

    // renew() 已迁移到 PermissionController: PUT /api/permissions/{id}/renew

    /**
     * 查询单个 license。仅平台管理员。
     */
    @GetMapping("/{id}")
    public ApiResponse<MerchantLicense> getById(@PathVariable String id) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        MerchantLicense license = licenseService.findById(id);
        if (license == null) {
            throw new BusinessException(ResultCode.License.NOT_FOUND);
        }
        // 不返回 license_secret 哈希
        license.setLicenseSecret(null);
        return ApiResponse.success(license);
    }

    private String extractClientIp(HttpServletRequest request) {
        String ip = request.getHeader("X-Forwarded-For");
        if (ip != null && !ip.isEmpty() && !"unknown".equalsIgnoreCase(ip)) {
            int comma = ip.indexOf(',');
            return comma > 0 ? ip.substring(0, comma).trim() : ip.trim();
        }
        ip = request.getHeader("X-Real-IP");
        if (ip != null && !ip.isEmpty() && !"unknown".equalsIgnoreCase(ip)) {
            return ip;
        }
        return request.getRemoteAddr();
    }
}
