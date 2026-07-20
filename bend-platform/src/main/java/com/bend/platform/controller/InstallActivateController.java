package com.bend.platform.controller;

import com.bend.platform.config.MasterModeCondition;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.dto.InstallActivateRequest;
import com.bend.platform.dto.InstallActivateResponse;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.service.InstallActivateService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Conditional;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 分控安装激活接口（总控侧，公开，不走 JWT）
 *
 * <p>分控安装器在商户机器上收集激活码后调用此接口，
 * 总控一步完成: 校验码 → 签发 License → 导出商户数据。
 *
 * <p>安全设计:
 * <ul>
 *   <li>不走 JWT 鉴权（安装器没有用户 Token）</li>
 *   <li>激活码即凭证: 持有有效未使用激活码 = 合法激活请求</li>
 *   <li>激活码一次性消费，激活后立即标记 used</li>
 *   <li>机器指纹绑定 License，防止分控包拷给多家使用</li>
 *   <li>IP 层面不限，因为商户可能在任何网络环境安装</li>
 * </ul>
 */
@Slf4j
@RestController
@RequestMapping("/api/install")
@RequiredArgsConstructor
@Conditional(MasterModeCondition.class)
public class InstallActivateController {

    private final InstallActivateService installActivateService;

    /**
     * 分控安装激活。
     *
     * <p>安装器传入激活码 + 本机指纹，总控返回 License 凭证 + 商户数据 SQL。
     * 总控地址从请求 Host 头反推（安装器调用时已填写正确的总控地址）。
     */
    @PostMapping("/activate")
    public ApiResponse<InstallActivateResponse> activate(@Valid @RequestBody InstallActivateRequest request,
                                                         HttpServletRequest httpRequest) {
        // 从请求推断总控地址（安装器填写的目标地址）
        String scheme = httpRequest.getScheme();
        String host = httpRequest.getHeader("Host");
        if (host == null || host.isBlank()) {
            throw new BusinessException(ResultCode.System.BAD_REQUEST, "无法获取总控地址");
        }
        String masterUrl = scheme + "://" + host;

        log.info("[安装激活] 收到激活请求 code={}*** fingerprint={}*** masterUrl={}",
                maskCode(request.getActivationCode()),
                maskFingerprint(request.getMachineFingerprint()),
                masterUrl);

        try {
            InstallActivateResponse resp = installActivateService.activate(request, masterUrl);
            log.info("[安装激活] 激活成功 merchantId={} licenseKey={}",
                    resp.getMerchantId(), resp.getLicenseKey());
            return ApiResponse.success("激活成功", resp);
        } catch (BusinessException e) {
            log.warn("[安装激活] 激活失败: {}", e.getMessage());
            throw e;
        } catch (Exception e) {
            log.error("[安装激活] 激活异常", e);
            throw new BusinessException(ResultCode.System.BAD_REQUEST, "激活失败: " + e.getMessage());
        }
    }

    private String maskCode(String code) {
        if (code == null || code.length() <= 6) return "***";
        return code.substring(0, 6) + "***";
    }

    private String maskFingerprint(String fp) {
        if (fp == null || fp.length() <= 8) return "***";
        return fp.substring(0, 8) + "***";
    }
}
