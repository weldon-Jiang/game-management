package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.dto.ActivationCodeBatchCodesPageRequest;
import com.bend.platform.dto.ActivationCodeBatchPageRequest;
import com.bend.platform.dto.ActivationCodeDto;
import com.bend.platform.dto.ActivationCodePageRequest;
import com.bend.platform.dto.ActivationCodeRequest;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.ActivationCode;
import com.bend.platform.entity.ActivationCodeBatch;
import com.bend.platform.entity.Merchant;
import com.bend.platform.entity.MerchantUser;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.ActivationCodeBatchMapper;
import com.bend.platform.repository.ActivationCodeMapper;
import com.bend.platform.repository.MerchantMapper;
import com.bend.platform.repository.MerchantUserMapper;
import com.bend.platform.service.ActivationCodeService;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import org.apache.ibatis.util.MapUtil;
import org.springframework.util.CollectionUtils;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.*;

import jakarta.validation.Valid;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 激活码控制器
 *
 * 功能说明：
 * - 管理VIP激活码
 * - 支持单个和批量生成激活码
 *
 * 主要功能：
 * - 生成单个激活码
 * - 批量生成激活码
 * - 查询激活码列表（分页）
 * - 使用激活码
 * - 删除激活码
 */
@RestController
@RequestMapping("/api/activation-codes")
@RequiredArgsConstructor
public class ActivationCodeController {

    private final ActivationCodeService activationCodeService;
    private final ActivationCodeMapper activationCodeMapper;
    private final ActivationCodeBatchMapper activationCodeBatchMapper;
    private final MerchantMapper merchantMapper;
    private final MerchantUserMapper merchantUserMapper;

    /**
     * 生成单个激活码
     *
     * @param request 激活码请求（包含vipType、merchantId等）
     * @return 创建的激活码
     */
    @PostMapping("/single")
    public ApiResponse<ActivationCode> generateSingle(@Valid @RequestBody ActivationCodeRequest request) {
        String currentMerchantId = UserContext.getMerchantId();

        String targetMerchantId;
        if (UserContext.isPlatformAdmin()) {
            targetMerchantId = request.getMerchantId() != null ? request.getMerchantId() : currentMerchantId;
        } else {
            targetMerchantId = currentMerchantId;
        }

        ActivationCodeBatch batch = activationCodeService.generateBatch(
                targetMerchantId,
                "SINGLE-" + System.currentTimeMillis(),
                request.getVipType(),
                1,
                request.getExpireTime()
        );
        LambdaQueryWrapper<ActivationCode> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(ActivationCode::getBatchId, batch.getId());
        ActivationCode code = activationCodeMapper.selectOne(wrapper);
        return ApiResponse.success("生成成功", code);
    }

    /**
     * 分页查询激活码列表
     *
     * @param request 分页请求参数
     * @return 激活码分页列表
     */
    @GetMapping("/list")
    public ApiResponse<IPage<ActivationCodeDto>> listCodes(ActivationCodePageRequest request) {

        if (!UserContext.isPlatformAdmin()) {
            request.setMerchantId(UserContext.getMerchantId());
        }

        IPage<ActivationCode> page = activationCodeService.findByMerchantId(
                request.getMerchantId(),
                request.getKeyword(),
                request);
        IPage<ActivationCodeDto> dtoPage = convertToDtoPage(page);
        return ApiResponse.success(dtoPage);
    }

    /**
     * 批量生成激活码
     *
     * @param request 批量生成请求（包含vipType、count、batchName等）
     * @return 创建的批次信息
     */
    @PostMapping("/batch")
    public ApiResponse<ActivationCodeBatch> generateBatch(@Valid @RequestBody ActivationCodeRequest request) {
        String currentMerchantId = UserContext.getMerchantId();

        String targetMerchantId;
        if (UserContext.isPlatformAdmin()) {
            targetMerchantId = request.getMerchantId() != null ? request.getMerchantId() : currentMerchantId;
        } else {
            targetMerchantId = currentMerchantId;
        }

        String batchName = StringUtils.hasText(request.getBatchName())
                ? request.getBatchName()
                : "BATCH-" + System.currentTimeMillis();

        ActivationCodeBatch batch = activationCodeService.generateBatch(
                targetMerchantId,
                batchName,
                request.getVipType(),
                request.getCount() != null ? request.getCount() : 1,
                request.getExpireTime()
        );
        return ApiResponse.success("生成成功", batch);
    }

    /**
     * 获取所有激活码批次
     *
     * @return 批次列表
     */
    @GetMapping("/batches")
    public ApiResponse<List<ActivationCodeBatch>> listBatches() {
        String merchantId = UserContext.isPlatformAdmin() ? null : UserContext.getMerchantId();
        List<ActivationCodeBatch> batches = activationCodeService.findAllBatchesByMerchantId(merchantId);
        return ApiResponse.success(batches);
    }

    /**
     * 分页查询激活码批次
     *
     * @param request 分页请求参数
     * @return 批次分页列表
     */
    @GetMapping("/batches/page")
    public ApiResponse<IPage<ActivationCodeBatch>> listBatchesPage(ActivationCodeBatchPageRequest request) {
        String merchantId = UserContext.isPlatformAdmin() ? null : UserContext.getMerchantId();
        IPage<ActivationCodeBatch> page = activationCodeService.findBatchesByMerchantId(
                merchantId,
                request);
        return ApiResponse.success(page);
    }

    /**
     * 获取批次详情
     *
     * @param batchId 批次ID
     * @return 批次信息
     */
    @GetMapping("/batch/{batchId}")
    public ApiResponse<ActivationCodeBatch> getBatchById(@PathVariable String batchId) {
        ActivationCodeBatch batch = activationCodeService.findBatchById(batchId);
        if (batch == null) {
            throw new BusinessException(ResultCode.ActivationCode.BATCH_NOT_FOUND);
        }

        if (!UserContext.isPlatformAdmin() && !batch.getMerchantId().equals(UserContext.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        return ApiResponse.success(batch);
    }

    /**
     * 获取批次下的激活码列表
     *
     * @param batchId 批次ID
     * @param request 分页请求参数
     * @return 激活码分页列表
     */
    @GetMapping("/batch/{batchId}/codes")
    public ApiResponse<IPage<ActivationCode>> listCodesByBatch(
            @PathVariable String batchId,
            ActivationCodeBatchCodesPageRequest request) {
        ActivationCodeBatch batch = activationCodeService.findBatchById(batchId);
        if (batch == null) {
            throw new BusinessException(ResultCode.ActivationCode.BATCH_NOT_FOUND);
        }

        if (!UserContext.isPlatformAdmin() && !batch.getMerchantId().equals(UserContext.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        IPage<ActivationCode> page = activationCodeService.findByBatchId(batchId, request);
        return ApiResponse.success(page);
    }

    /**
     * 使用激活码
     * 商户用户调用，将激活码标记为已使用
     *
     * @param code 激活码
     * @return 使用后的激活码信息
     */
    @PostMapping("/use")
    public ApiResponse<ActivationCode> useCode(@RequestParam String code) {
        String userId = UserContext.getUserId();
        ActivationCode result = activationCodeService.useCode(code, userId);
        return ApiResponse.success("激活成功", result);
    }

    /**
     * 删除激活码
     * 仅平台管理员可操作
     *
     * @param ids 激活码ID列表
     * @return 操作结果
     */
    @DeleteMapping
    public ApiResponse<Void> deleteCodes(@RequestBody List<String> ids) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        activationCodeService.deleteByIds(ids);
        return ApiResponse.success("删除成功", null);
    }

    /**
     * 转换为DTO分页
     *
     * @param page 原始分页
     * @return DTO分页
     */
    private IPage<ActivationCodeDto> convertToDtoPage(IPage<ActivationCode> page) {
        List<ActivationCode> records = page.getRecords();
        if (CollectionUtils.isEmpty(records)) {
            return new Page<>(page.getCurrent(), page.getSize(), page.getTotal());
        }

        List<String> merchantIds = records.stream()
                .map(ActivationCode::getMerchantId)
                .filter(StringUtils::hasText)
                .distinct()
                .collect(Collectors.toList());

        List<String> userIds = records.stream()
                .map(ActivationCode::getUsedBy)
                .filter(StringUtils::hasText)
                .distinct()
                .collect(Collectors.toList());

        Map<String, String> merchantNameMap = new HashMap<>();
        if (!CollectionUtils.isEmpty(merchantIds)) {
            LambdaQueryWrapper<Merchant> wrapper = new LambdaQueryWrapper<>();
            wrapper.in(Merchant::getId, merchantIds);
            merchantMapper.selectList(wrapper).forEach(m -> merchantNameMap.put(m.getId(), m.getName()));
        }

        Map<String, String> userNameMap = new HashMap<>();
        if (!CollectionUtils.isEmpty(userIds)) {
            LambdaQueryWrapper<MerchantUser> wrapper = new LambdaQueryWrapper<>();
            wrapper.in(MerchantUser::getId, userIds);
            merchantUserMapper.selectList(wrapper).forEach(u -> userNameMap.put(u.getId(), u.getUsername()));
        }

        List<String> batchIds = records.stream()
                .map(ActivationCode::getBatchId)
                .filter(StringUtils::hasText)
                .distinct()
                .collect(Collectors.toList());

        Map<String, ActivationCodeBatch> batchMap = new HashMap<>();
        if (!CollectionUtils.isEmpty(batchIds)) {
            LambdaQueryWrapper<ActivationCodeBatch> batchWrapper = new LambdaQueryWrapper<>();
            batchWrapper.in(ActivationCodeBatch::getId, batchIds);
            activationCodeBatchMapper.selectList(batchWrapper).forEach(b -> batchMap.put(b.getId(), b));
        }

        List<ActivationCodeDto> dtos = records.stream().map(code -> {
            ActivationCodeDto dto = new ActivationCodeDto();
            dto.setId(code.getId());
            dto.setMerchantId(code.getMerchantId());
            dto.setBatchId(code.getBatchId());
            dto.setCode(code.getCode());
            dto.setStatus(code.getStatus());
            dto.setUsedBy(code.getUsedBy());
            dto.setUsedTime(code.getUsedTime());
            dto.setExpireTime(code.getExpireTime());
            dto.setGeneratedTime(code.getGeneratedTime());
            dto.setCreatedTime(code.getCreatedTime());
            dto.setUpdatedTime(code.getUpdatedTime());
            dto.setMerchantName(merchantNameMap.get(code.getMerchantId()));
            dto.setUsedByName(userNameMap.get(code.getUsedBy()));

            ActivationCodeBatch batch = batchMap.get(code.getBatchId());
            if (batch != null) {
                dto.setVipType(batch.getVipType());
            }
            return dto;
        }).collect(Collectors.toList());

        Page<ActivationCodeDto> result = new Page<>(page.getCurrent(), page.getSize(), page.getTotal());
        result.setRecords(dtos);
        return result;
    }
}