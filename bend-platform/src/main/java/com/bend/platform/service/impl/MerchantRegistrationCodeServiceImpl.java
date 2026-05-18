package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.dto.MerchantRegistrationCodePageRequest;
import com.bend.platform.entity.AgentInstance;
import com.bend.platform.entity.Merchant;
import com.bend.platform.entity.MerchantRegistrationCode;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.AgentInstanceMapper;
import com.bend.platform.repository.MerchantMapper;
import com.bend.platform.repository.MerchantRegistrationCodeMapper;
import com.bend.platform.service.MerchantRegistrationCodeService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.CollectionUtils;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

/**
 * 商户注册码服务实现类
 *
 * 功能说明：
 * - 管理Agent注册码
 * - 用于Agent首次注册到系统
 *
 * 主要功能：
 * - 生成注册码
 * - 验证注册码
 * - 激活注册码
 * - 分页查询注册码
 * - 删除注册码
 */
@Slf4j
@Service
public class MerchantRegistrationCodeServiceImpl implements MerchantRegistrationCodeService {

    private final MerchantRegistrationCodeMapper registrationCodeMapper;
    private final MerchantMapper merchantMapper;
    private final AgentInstanceMapper agentInstanceMapper;
    
    @Autowired(required = false)
    private StringRedisTemplate redisTemplate;

    public MerchantRegistrationCodeServiceImpl(MerchantRegistrationCodeMapper registrationCodeMapper, 
                                               MerchantMapper merchantMapper,
                                               AgentInstanceMapper agentInstanceMapper) {
        this.registrationCodeMapper = registrationCodeMapper;
        this.merchantMapper = merchantMapper;
        this.agentInstanceMapper = agentInstanceMapper;
    }

    private static final String CODE_PREFIX = "AGENT";
    private static final int CODE_LENGTH = 12;
    private static final String FAILED_ATTEMPT_KEY_PREFIX = "reg_code:failed:";
    private static final int MAX_FAILED_ATTEMPTS = 5;
    private static final int FAILED_ATTEMPT_WINDOW_MINUTES = 30;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public List<String> generateCodes(String merchantId, int count) {
        Merchant merchant = merchantMapper.selectById(merchantId);
        if (merchant == null) {
            throw new BusinessException(ResultCode.Merchant.NOT_FOUND);
        }

        List<String> codes = new ArrayList<>();

        for (int i = 0; i < count; i++) {
            MerchantRegistrationCode registrationCode = new MerchantRegistrationCode();
            registrationCode.setMerchantId(merchantId);
            registrationCode.setCode(generateUniqueCode());
            registrationCode.setStatus("unused");
            registrationCode.setCreatedTime(LocalDateTime.now());

            registrationCodeMapper.insert(registrationCode);
            codes.add(registrationCode.getCode());
        }

        log.info("生成注册码成功 - 商户ID: {}, 数量: {}, 第一个码: {}",
                merchantId, count, CollectionUtils.isEmpty(codes) ? "N/A" : codes.get(0));

        return codes;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public ActivationResult activateCode(String code, String agentId, String agentSecret) {
        if (isExcessiveAttempts(code)) {
            log.warn("注册码激活失败 - 失败次数超限: {}", code);
            return ActivationResult.failure("注册码验证失败次数过多，请稍后再试");
        }

        MerchantRegistrationCode registrationCode = findByCode(code);

        if (registrationCode == null) {
            log.warn("注册码激活失败 - 注册码不存在: {}", code);
            recordFailedAttempt(code);
            return ActivationResult.failure("注册码不存在");
        }

        if ("used".equals(registrationCode.getStatus())) {
            log.warn("注册码激活失败 - 已被使用: {}", code);
            recordFailedAttempt(code);
            return ActivationResult.failure("注册码已被使用");
        }

        if (registrationCode.getExpireTime() != null &&
                registrationCode.getExpireTime().isBefore(LocalDateTime.now())) {
            log.warn("注册码激活失败 - 已过期: {}", code);
            recordFailedAttempt(code);
            return ActivationResult.failure("注册码已过期");
        }

        String merchantId = registrationCode.getMerchantId();
        registrationCode.setStatus("used");
        registrationCode.setUsedTime(LocalDateTime.now());
        registrationCode.setUsedByAgentId(agentId);
        registrationCode.setAgentId(agentId);
        registrationCodeMapper.updateById(registrationCode);

        log.info("注册码激活成功 - 注册码: {}, AgentID: {}, 商户ID: {}", code, agentId, merchantId);

        return ActivationResult.success(merchantId);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public ActivationResult activateCodeWithSystemInfo(String code, String agentId, String agentSecret, String systemInfo) {
        if (isExcessiveAttempts(code)) {
            log.warn("注册码激活失败 - 失败次数超限: {}", code);
            return ActivationResult.failure("注册码验证失败次数过多，请稍后再试");
        }

        MerchantRegistrationCode registrationCode = findByCode(code);

        if (registrationCode == null) {
            log.warn("注册码激活失败 - 注册码不存在: {}", code);
            recordFailedAttempt(code);
            return ActivationResult.failure("注册码不存在");
        }

        if ("used".equals(registrationCode.getStatus())) {
            log.warn("注册码激活失败 - 已被使用: {}", code);
            recordFailedAttempt(code);
            return ActivationResult.failure("注册码已被使用");
        }

        if (registrationCode.getExpireTime() != null &&
                registrationCode.getExpireTime().isBefore(LocalDateTime.now())) {
            log.warn("注册码激活失败 - 已过期: {}", code);
            recordFailedAttempt(code);
            return ActivationResult.failure("注册码已过期");
        }

        String merchantId = registrationCode.getMerchantId();
        
        registrationCode.setStatus("used");
        registrationCode.setUsedTime(LocalDateTime.now());
        registrationCode.setUsedByAgentId(agentId);
        registrationCode.setAgentId(agentId);
        registrationCodeMapper.updateById(registrationCode);

        updateAgentInstanceWithSystemInfo(agentId, agentSecret, merchantId, code, systemInfo);

        log.info("注册码激活成功（带系统信息）- 注册码: {}, AgentID: {}, 商户ID: {}", code, agentId, merchantId);

        return ActivationResult.success(merchantId);
    }

    private void updateAgentInstanceWithSystemInfo(String agentId, String agentSecret, 
                                                   String merchantId, String registrationCode, String systemInfo) {
        try {
            AgentInstance existing = agentInstanceMapper.selectOne(
                new LambdaQueryWrapper<AgentInstance>().eq(AgentInstance::getAgentId, agentId)
            );

            if (existing != null) {
                existing.setAgentSecret(agentSecret);
                existing.setMerchantId(merchantId);
                existing.setRegistrationCode(registrationCode);
                existing.setStatus("offline");
                existing.setUpdatedTime(LocalDateTime.now());

                if (systemInfo != null && !systemInfo.isEmpty()) {
                    ObjectMapper mapper = new ObjectMapper();
                    JsonNode node = mapper.readTree(systemInfo);
                    
                    existing.setOsType(getJsonNodeValue(node, "osType"));
                    existing.setOsVersion(getJsonNodeValue(node, "osVersion"));
                    existing.setCpuCount(getJsonNodeIntValue(node, "cpuCount"));
                    existing.setMaxConcurrentTasks(getJsonNodeIntValue(node, "maxConcurrentTasks"));
                }

                agentInstanceMapper.updateById(existing);
                log.info("Agent实例更新成功，包含系统信息 - AgentID: {}", agentId);
            } else {
                AgentInstance agentInstance = new AgentInstance();
                agentInstance.setAgentId(agentId);
                agentInstance.setAgentSecret(agentSecret);
                agentInstance.setMerchantId(merchantId);
                agentInstance.setRegistrationCode(registrationCode);
                agentInstance.setStatus("offline");
                agentInstance.setCreatedTime(LocalDateTime.now());
                agentInstance.setUpdatedTime(LocalDateTime.now());

                if (systemInfo != null && !systemInfo.isEmpty()) {
                    ObjectMapper mapper = new ObjectMapper();
                    JsonNode node = mapper.readTree(systemInfo);
                    
                    agentInstance.setOsType(getJsonNodeValue(node, "osType"));
                    agentInstance.setOsVersion(getJsonNodeValue(node, "osVersion"));
                    agentInstance.setCpuCount(getJsonNodeIntValue(node, "cpuCount"));
                    agentInstance.setMaxConcurrentTasks(getJsonNodeIntValue(node, "maxConcurrentTasks"));
                }

                agentInstanceMapper.insert(agentInstance);
                log.info("Agent实例创建成功，包含系统信息 - AgentID: {}", agentId);
            }
            
        } catch (Exception e) {
            log.error("创建/更新Agent实例失败 - AgentID: {}, 错误: {}", agentId, e.getMessage());
        }
    }

    private String getJsonNodeValue(JsonNode node, String fieldName) {
        JsonNode valueNode = node.get(fieldName);
        return valueNode != null && !valueNode.isNull() ? valueNode.asText() : null;
    }

    private Integer getJsonNodeIntValue(JsonNode node, String fieldName) {
        JsonNode valueNode = node.get(fieldName);
        return valueNode != null && !valueNode.isNull() && valueNode.isNumber() ? valueNode.asInt() : null;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public ActivationResult validateAndConsume(String code) {
        if (isExcessiveAttempts(code)) {
            log.warn("注册码验证失败 - 失败次数超限: {}", code);
            return ActivationResult.failure("注册码验证失败次数过多，请稍后再试");
        }

        MerchantRegistrationCode registrationCode = findByCode(code);

        if (registrationCode == null) {
            log.warn("注册码验证失败 - 注册码不存在: {}", code);
            recordFailedAttempt(code);
            return ActivationResult.failure("注册码不存在");
        }

        if ("used".equals(registrationCode.getStatus())) {
            log.warn("注册码验证失败 - 已被使用: {}", code);
            recordFailedAttempt(code);
            return ActivationResult.failure("注册码已被使用");
        }

        if (registrationCode.getExpireTime() != null &&
                registrationCode.getExpireTime().isBefore(LocalDateTime.now())) {
            log.warn("注册码验证失败 - 已过期: {}", code);
            recordFailedAttempt(code);
            return ActivationResult.failure("注册码已过期");
        }

        String merchantId = registrationCode.getMerchantId();

        registrationCode.setStatus("used");
        registrationCode.setUsedTime(LocalDateTime.now());
        registrationCodeMapper.updateById(registrationCode);

        log.info("注册码验证并消费成功 - 注册码: {}, 商户ID: {}", code, merchantId);

        return ActivationResult.success(merchantId);
    }

    @Override
    public MerchantRegistrationCode validateCode(String code) {
        MerchantRegistrationCode registrationCode = findByCode(code);

        if (registrationCode == null) {
            throw new BusinessException(ResultCode.RegistrationCode.NOT_FOUND);
        }

        if ("used".equals(registrationCode.getStatus())) {
            throw new BusinessException(ResultCode.RegistrationCode.ALREADY_USED);
        }

        if (registrationCode.getExpireTime() != null &&
                registrationCode.getExpireTime().isBefore(LocalDateTime.now())) {
            throw new BusinessException(ResultCode.RegistrationCode.EXPIRED);
        }

        return registrationCode;
    }

    @Override
    public IPage<MerchantRegistrationCode> findByMerchantId(String merchantId, MerchantRegistrationCodePageRequest request) {
        return findByMerchantId(merchantId, null, request);
    }

    @Override
    public IPage<MerchantRegistrationCode> findByMerchantId(String merchantId, String keyword, MerchantRegistrationCodePageRequest request) {
        LambdaQueryWrapper<MerchantRegistrationCode> wrapper = new LambdaQueryWrapper<>();
        if (StringUtils.hasText(merchantId)) {
            wrapper.eq(MerchantRegistrationCode::getMerchantId, merchantId);
        }
        if (StringUtils.hasText(keyword)) {
            wrapper.like(MerchantRegistrationCode::getCode, keyword);
        }
        wrapper.orderByDesc(MerchantRegistrationCode::getCreatedTime);
        Page<MerchantRegistrationCode> page = new Page<>(request.getPageNum(), request.getPageSize(), true);
        return registrationCodeMapper.selectPage(page, wrapper);
    }

    @Override
    public MerchantRegistrationCode findByCode(String code) {
        LambdaQueryWrapper<MerchantRegistrationCode> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(MerchantRegistrationCode::getCode, code);
        return registrationCodeMapper.selectOne(wrapper);
    }

    @Override
    public void deleteByIds(List<String> ids) {
        if (CollectionUtils.isEmpty(ids)) {
            return;
        }
        for (String id : ids) {
            MerchantRegistrationCode code = registrationCodeMapper.selectById(id);
            if (code != null && "unused".equals(code.getStatus())) {
                registrationCodeMapper.deleteById(id);
            }
        }
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void unbindByAgentId(String agentId) {
        LambdaQueryWrapper<MerchantRegistrationCode> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(MerchantRegistrationCode::getAgentId, agentId);
        List<MerchantRegistrationCode> codes = registrationCodeMapper.selectList(wrapper);

        for (MerchantRegistrationCode code : codes) {
            code.setStatus("unused");
            code.setUsedByAgentId(null);
            code.setAgentId(null);
            code.setUsedTime(null);
            registrationCodeMapper.updateById(code);
            log.info("注册码解绑 - ID: {}, 注册码: {}, AgentID: {}", code.getId(), code.getCode(), agentId);
        }
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void resetCode(String id) {
        MerchantRegistrationCode code = registrationCodeMapper.selectById(id);
        if (code == null) {
            throw new BusinessException(ResultCode.RegistrationCode.NOT_FOUND);
        }
        code.setStatus("unused");
        code.setUsedByAgentId(null);
        code.setAgentId(null);
        code.setUsedTime(null);
        registrationCodeMapper.updateById(code);
        log.info("注册码重置成功 - ID: {}, 注册码: {}", id, code.getCode());
    }

    private String generateUniqueCode() {
        String uuid = UUID.randomUUID().toString().replace("-", "").toUpperCase();
        String part1 = uuid.substring(0, 4);
        String part2 = uuid.substring(4, 8);
        String part3 = uuid.substring(8, 12);
        return CODE_PREFIX + "-" + part1 + "-" + part2 + "-" + part3;
    }

    @Override
    public boolean isExcessiveAttempts(String code) {
        if (redisTemplate == null) {
            return false;
        }
        String key = FAILED_ATTEMPT_KEY_PREFIX + code;
        String countStr = redisTemplate.opsForValue().get(key);
        if (countStr == null) {
            return false;
        }
        int count = Integer.parseInt(countStr);
        return count >= MAX_FAILED_ATTEMPTS;
    }

    @Override
    public void recordFailedAttempt(String code) {
        if (redisTemplate == null) {
            log.warn("注册码激活失败 - 注册码: {}, Redis不可用，无法记录失败次数", code);
            return;
        }
        String key = FAILED_ATTEMPT_KEY_PREFIX + code;
        Long count = redisTemplate.opsForValue().increment(key);
        if (count != null && count == 1) {
            redisTemplate.expire(key, FAILED_ATTEMPT_WINDOW_MINUTES, TimeUnit.MINUTES);
        }
        log.warn("注册码激活失败记录 - 注册码: {}, 失败次数: {}", code, count);
    }
}