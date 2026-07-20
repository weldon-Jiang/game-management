package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.config.MasterModeCondition;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.dto.MerchantRegistrationCodeDto;
import com.bend.platform.dto.MerchantRegistrationCodePageRequest;
import com.bend.platform.entity.MerchantRegistrationCode;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.service.AgentInstanceService;
import com.bend.platform.service.MerchantRegistrationCodeService;
import com.bend.platform.service.MerchantService;
import com.bend.platform.service.MerchantRegistrationCodeService.ActivationResult;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Conditional;
import org.springframework.util.CollectionUtils;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 分控安装注册码控制器（总控侧）。
 *
 * <p>注册码由总控为商户签发，供分控平台安装激活时使用；
 * Agent 已改为 UDP 自动发现注册，不再使用注册码。
 */
@Slf4j
@RestController
@RequestMapping("/api/registration-codes")
@RequiredArgsConstructor
@Conditional(MasterModeCondition.class)
public class MerchantRegistrationCodeController {

    private final MerchantRegistrationCodeService registrationCodeService;
    private final MerchantService merchantService;
    private final AgentInstanceService agentInstanceService;

    /**
     * 生成分控安装注册码（兼容旧接口，等价于 {@link #generateInstallCode(Map)}）。
     *
     * @deprecated 请使用 {@code POST /api/registration-codes/generate-install}。
     */
    @Deprecated
    @PostMapping("/generate")
    public ApiResponse<List<String>> generateCodes(@RequestBody Map<String, Object> request) {
        if (!UserContext.isPlatformAdmin()) {
            return ApiResponse.error(403, "仅平台管理员可生成安装注册码");
        }
        String merchantId = (String) request.get("merchantId");
        if (!StringUtils.hasText(merchantId)) {
            return ApiResponse.error(400, "请选择商户");
        }
        String code = registrationCodeService.generateInstallCode(merchantId);
        return ApiResponse.success("生成成功", List.of(code));
    }

    /**
     * 生成分控安装注册码（每商户一个未使用码，永久有效）。
     * 仅总控平台管理员可操作。
     *
     * @param request 请求体（包含 merchantId）
     * @return 注册码字符串（形如 BEND-INSTALL-XXXXXXXX）
     */
    @PostMapping("/generate-install")
    public ApiResponse<String> generateInstallCode(@RequestBody Map<String, Object> request) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.System.FORBIDDEN, "仅平台管理员可生成安装注册码");
        }
        String merchantId = (String) request.get("merchantId");
        if (!StringUtils.hasText(merchantId)) {
            throw new BusinessException(ResultCode.System.BAD_REQUEST, "请选择商户");
        }
        String code = registrationCodeService.generateInstallCode(merchantId);
        return ApiResponse.success("生成成功", code);
    }

    /**
     * 激活注册码（Agent 注册用，已废弃）
     *
     * @param request 请求体
     * @return 激活结果
     * @deprecated Agent 已改为 UDP 自动发现 + auto-register，不再使用注册码激活。
     */
    @Deprecated
    @PostMapping("/activate")
    public ApiResponse<ActivationResult> activate(@RequestBody Map<String, Object> request) {
        String code = (String) request.get("code");
        String agentId = (String) request.get("agentId");
        String agentSecret = (String) request.get("agentSecret");
        Object systemInfoObj = request.get("systemInfo");
        
        String systemInfo = null;
        if (systemInfoObj != null) {
            if (systemInfoObj instanceof String) {
                systemInfo = (String) systemInfoObj;
            } else {
                try {
                    com.fasterxml.jackson.databind.ObjectMapper mapper = new com.fasterxml.jackson.databind.ObjectMapper();
                    systemInfo = mapper.writeValueAsString(systemInfoObj);
                } catch (Exception e) {
                    // 序列化失败，不使用systemInfo
                }
            }
        }

        if (code == null || code.isEmpty()) {
            return ApiResponse.error(400, "注册码不能为空");
        }

        ActivationResult result;
        if (systemInfo != null && !systemInfo.isEmpty()) {
            result = registrationCodeService.activateCodeWithSystemInfo(code, agentId, agentSecret, systemInfo);
        } else {
            result = registrationCodeService.activateCode(code, agentId, agentSecret);
        }

        if (result.isSuccess()) {
            return ApiResponse.success("激活成功", result);
        } else {
            return ApiResponse.error(400, result.getMessage());
        }
    }

    /**
     * 分页查询注册码列表
     * 平台管理员可查询所有商户的注册码，商户用户只能查询本商户
     *
     * @param request 分页请求参数
     * @return 注册码分页列表
     */
    @GetMapping("/list")
    public ApiResponse<IPage<MerchantRegistrationCodeDto>> listCodes(MerchantRegistrationCodePageRequest request) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.System.FORBIDDEN, "仅平台管理员可查看安装注册码");
        }

        IPage<MerchantRegistrationCode> page = registrationCodeService.findByMerchantId(
                request.getMerchantId(),
                request.getKeyword(),
                request);
        IPage<MerchantRegistrationCodeDto> dtoPage = convertToDtoPage(page);
        return ApiResponse.success(dtoPage);
    }

    /**
     * 验证注册码
     *
     * @param code 注册码
     * @return 注册码详情
     */
    @GetMapping("/validate/{code}")
    public ApiResponse<MerchantRegistrationCode> validateCode(@PathVariable String code) {
        MerchantRegistrationCode registrationCode = registrationCodeService.validateCode(code);
        return ApiResponse.success(registrationCode);
    }

    /**
     * 检查注册码是否有效
     *
     * @param code 注册码
     * @return 验证结果
     */
    @GetMapping("/check/{code}")
    public ApiResponse<Map<String, Object>> checkCode(@PathVariable String code) {
        try {
            MerchantRegistrationCode registrationCode = registrationCodeService.validateCode(code);
            Map<String, Object> result = new HashMap<>();
            result.put("valid", true);
            result.put("merchantId", registrationCode.getMerchantId());
            result.put("status", registrationCode.getStatus());
            return ApiResponse.success(result);
        } catch (Exception e) {
            Map<String, Object> result = new HashMap<>();
            result.put("valid", false);
            result.put("message", e.getMessage());
            return ApiResponse.success(result);
        }
    }

    /**
     * 删除注册码
     * 仅平台管理员可操作
     *
     * @param ids 注册码ID列表
     * @return 操作结果
     */
    @DeleteMapping
    public ApiResponse<Void> deleteCodes(@RequestBody List<String> ids) {
        if (!UserContext.isPlatformAdmin()) {
            return ApiResponse.error(403, "无权限删除");
        }
        registrationCodeService.deleteByIds(ids);
        return ApiResponse.success("删除成功", null);
    }

    /**
     * 转换为DTO分页
     *
     * @param page 原始分页
     * @return DTO分页
     */
    private IPage<MerchantRegistrationCodeDto> convertToDtoPage(IPage<MerchantRegistrationCode> page) {
        List<MerchantRegistrationCode> records = page.getRecords();
        if (CollectionUtils.isEmpty(records)) {
            return new Page<>(page.getCurrent(), page.getSize(), page.getTotal());
        }

        List<String> merchantIds = records.stream()
                .map(MerchantRegistrationCode::getMerchantId)
                .filter(StringUtils::hasText)
                .distinct()
                .collect(Collectors.toList());

        Map<String, String> merchantNameMap = new HashMap<>();
        if (!CollectionUtils.isEmpty(merchantIds)) {
            merchantService.findByIds(merchantIds).forEach(m -> merchantNameMap.put(m.getId(), m.getName()));
        }

        List<String> agentIds = records.stream()
                .flatMap(code -> java.util.stream.Stream.of(code.getUsedByAgentId(), code.getAgentId()))
                .filter(StringUtils::hasText)
                .distinct()
                .collect(Collectors.toList());
        Map<String, String> agentNameMap = agentInstanceService.resolveDisplayNames(agentIds);

        List<MerchantRegistrationCodeDto> dtos = records.stream().map(code -> {
            MerchantRegistrationCodeDto dto = new MerchantRegistrationCodeDto();
            dto.setId(code.getId());
            dto.setMerchantId(code.getMerchantId());
            dto.setMerchantName(merchantNameMap.get(code.getMerchantId()));
            dto.setCode(code.getCode());
            dto.setStatus(code.getStatus());
            dto.setUsedByAgentId(code.getUsedByAgentId());
            if (StringUtils.hasText(code.getUsedByAgentId())) {
                dto.setUsedByAgentName(agentNameMap.get(code.getUsedByAgentId()));
            }
            dto.setAgentId(code.getAgentId());
            if (StringUtils.hasText(code.getAgentId())) {
                dto.setAgentName(agentNameMap.get(code.getAgentId()));
            }
            dto.setCreatedTime(code.getCreatedTime());
            dto.setExpireTime(code.getExpireTime());
            dto.setUsedTime(code.getUsedTime());
            return dto;
        }).collect(Collectors.toList());

        Page<MerchantRegistrationCodeDto> result = new Page<>(page.getCurrent(), page.getSize(), page.getTotal());
        result.setRecords(dtos);
        return result;
    }
}