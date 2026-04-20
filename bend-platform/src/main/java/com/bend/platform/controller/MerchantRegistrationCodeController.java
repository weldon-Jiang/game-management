package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.dto.MerchantRegistrationCodeDto;
import com.bend.platform.dto.MerchantRegistrationCodePageRequest;
import com.bend.platform.entity.Merchant;
import com.bend.platform.entity.MerchantRegistrationCode;
import com.bend.platform.repository.MerchantMapper;
import com.bend.platform.service.MerchantRegistrationCodeService;
import com.bend.platform.service.MerchantRegistrationCodeService.ActivationResult;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import org.springframework.util.CollectionUtils;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 商户注册码控制器
 *
 * 功能说明：
 * - 管理Agent注册码
 * - 用于Agent首次注册到系统
 *
 * 主要功能：
 * - 生成注册码
 * - 激活注册码
 * - 查询注册码列表（分页）
 * - 验证注册码
 * - 删除注册码
 */
@RestController
@RequestMapping("/api/registration-codes")
@RequiredArgsConstructor
public class MerchantRegistrationCodeController {

    private final MerchantRegistrationCodeService registrationCodeService;
    private final MerchantMapper merchantMapper;

    /**
     * 生成注册码
     * 平台管理员可指定商户，非平台管理员自动使用当前用户商户
     *
     * @param request 请求体（包含merchantId和count）
     * @return 生成的注册码列表
     */
    @PostMapping("/generate")
    public ApiResponse<List<String>> generateCodes(@RequestBody Map<String, Object> request) {
        String merchantIdFromRequest = (String) request.get("merchantId");
        Integer count = (Integer) request.getOrDefault("count", 1);

        String merchantId;
        if (UserContext.isPlatformAdmin()) {
            if (merchantIdFromRequest == null || merchantIdFromRequest.isEmpty()) {
                return ApiResponse.error(400, "管理员生成注册码必须选择商户");
            }
            merchantId = merchantIdFromRequest;
        } else {
            merchantId = UserContext.getMerchantId();
        }

        List<String> codes = registrationCodeService.generateCodes(merchantId, count);
        return ApiResponse.success("生成成功", codes);
    }

    /**
     * 激活注册码
     * Agent注册时调用，验证注册码有效性
     *
     * @param request 请求体（包含code、agentId、agentSecret）
     * @return 激活结果
     */
    @PostMapping("/activate")
    public ApiResponse<ActivationResult> activate(@RequestBody Map<String, String> request) {
        String code = request.get("code");
        String agentId = request.get("agentId");
        String agentSecret = request.get("agentSecret");

        if (code == null || code.isEmpty()) {
            return ApiResponse.error(400, "注册码不能为空");
        }

        ActivationResult result = registrationCodeService.activateCode(code, agentId, agentSecret);

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

        String currentMerchantId = UserContext.getMerchantId();

        if (!UserContext.isPlatformAdmin()) {
            request.setMerchantId(currentMerchantId);
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
            LambdaQueryWrapper<Merchant> wrapper = new LambdaQueryWrapper<>();
            wrapper.in(Merchant::getId, merchantIds);
            merchantMapper.selectList(wrapper).forEach(m -> merchantNameMap.put(m.getId(), m.getName()));
        }

        List<MerchantRegistrationCodeDto> dtos = records.stream().map(code -> {
            MerchantRegistrationCodeDto dto = new MerchantRegistrationCodeDto();
            dto.setId(code.getId());
            dto.setMerchantId(code.getMerchantId());
            dto.setMerchantName(merchantNameMap.get(code.getMerchantId()));
            dto.setCode(code.getCode());
            dto.setStatus(code.getStatus());
            dto.setUsedByAgentId(code.getUsedByAgentId());
            dto.setAgentId(code.getAgentId());
            dto.setCreatedAt(code.getCreatedAt());
            dto.setExpireTime(code.getExpireTime());
            dto.setUsedAt(code.getUsedAt());
            return dto;
        }).collect(Collectors.toList());

        Page<MerchantRegistrationCodeDto> result = new Page<>(page.getCurrent(), page.getSize(), page.getTotal());
        result.setRecords(dtos);
        return result;
    }
}