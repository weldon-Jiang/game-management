package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.dto.ImportResultDto;
import com.bend.platform.dto.StreamingAccountImportDto;
import com.bend.platform.dto.StreamingAccountPageRequest;
import com.bend.platform.entity.StreamingAccount;
import com.bend.platform.enums.PlatformType;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.StreamingAccountMapper;
import com.bend.platform.service.MerchantService;
import com.bend.platform.service.StreamingAccountService;
import com.bend.platform.util.AesUtil;
import com.bend.platform.util.DataSecurityUtil;
import com.bend.platform.util.PlatformTypeUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.CollectionUtils;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * 流媒体账号服务实现类
 *
 * 功能说明：
 * - 管理Xbox流媒体账号的CRUD操作
 * - 支持多个流媒体平台账号的管理
 *
 * 主要功能：
 * - 创建流媒体账号
 * - 分页查询账号
 * - 根据商户ID查询账号
 * - 更新账号信息
 * - 更新AgentID
 * - 删除账号
 *
 * 依赖注入：
 * - 使用Lombok的@RequiredArgsConstructor注解
 * - 为所有 final字段生成构造器进行依赖注入
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class StreamingAccountServiceImpl implements StreamingAccountService {

    private final StreamingAccountMapper streamingAccountMapper;
    private final MerchantService merchantService;
    private final AesUtil aesUtil;
    private final DataSecurityUtil dataSecurityUtil;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public StreamingAccount create(String merchantId, String name, String email, String password, String authCode, String platform) {
        // 校验商户是否有效
        merchantService.validateMerchantActive(merchantId);

        // 检查邮箱是否已被使用
        if (findByEmail(email) != null) {
            throw new BusinessException(ResultCode.StreamingAccount.EMAIL_DUPLICATE);
        }

        // 检查名称是否已被使用
        if (findByName(name) != null) {
            throw new BusinessException(ResultCode.StreamingAccount.NAME_DUPLICATE);
        }

        StreamingAccount account = new StreamingAccount();
        account.setMerchantId(merchantId);
        account.setName(name);
        account.setEmail(email);
        account.setPasswordEncrypted(aesUtil.encrypt(password));
        account.setAuthCode(authCode);
        account.setPlatform(PlatformTypeUtil.requireValid(platform));
        account.setStatus("idle");

        streamingAccountMapper.insert(account);
        log.info("创建流媒体账号成功 - ID: {}, 邮箱: {}", account.getId(), email);
        return account;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public ImportResultDto batchImport(String merchantId, List<StreamingAccountImportDto> accounts) {
        ImportResultDto result = new ImportResultDto();
        List<String> errors = new ArrayList<>();
        int successCount = 0;
        int skipCount = 0;

        if (CollectionUtils.isEmpty(accounts)) {
            errors.add("导入数据不能为空");
            result.setFailCount(accounts != null ? accounts.size() : 0);
            result.setErrors(errors);
            return result;
        }

        merchantService.validateMerchantActive(merchantId);

        Set<String> emailSet = new HashSet<>();
        Set<String> nameSet = new HashSet<>();
        Set<String> existEmails = new HashSet<>();
        Set<String> existNames = new HashSet<>();
        List<StreamingAccountImportDto> toImport = new ArrayList<>();

        for (int i = 0; i < accounts.size(); i++) {
            StreamingAccountImportDto dto = accounts.get(i);
            int rowNum = i + 2;

            if (emailSet.contains(dto.getEmail())) {
                errors.add(String.format("第%d行: 邮箱[%s]重复", rowNum, dto.getEmail()));
                continue;
            }

            if (nameSet.contains(dto.getName())) {
                errors.add(String.format("第%d行: 账号名称[%s]重复", rowNum, dto.getName()));
                continue;
            }

            if (dto.getPlatform() != null && !dto.getPlatform().isBlank()
                    && PlatformType.fromCode(dto.getPlatform()) == null) {
                errors.add(String.format("第%d行: 平台类型无效，仅支持 xbox、playstation", rowNum));
                continue;
            }

            StreamingAccount existingByEmail = findByEmail(dto.getEmail());
            if (existingByEmail != null) {
                existEmails.add(dto.getEmail());
                skipCount++;
                continue;
            }

            StreamingAccount existingByName = findByName(dto.getName());
            if (existingByName != null) {
                existNames.add(dto.getName());
                skipCount++;
                continue;
            }

            emailSet.add(dto.getEmail());
            nameSet.add(dto.getName());
            toImport.add(dto);
        }

        for (StreamingAccountImportDto dto : toImport) {
            try {
                StreamingAccount entity = new StreamingAccount();
                entity.setMerchantId(merchantId);
                entity.setName(dto.getName());
                entity.setEmail(dto.getEmail());
                entity.setPasswordEncrypted(aesUtil.encrypt(dto.getPassword()));
                entity.setAuthCode(dto.getAuthCode());
                entity.setPlatform(PlatformTypeUtil.normalizeOrDefault(dto.getPlatform()));
                entity.setStatus("idle");
                entity.setCreatedTime(LocalDateTime.now());
                entity.setUpdatedTime(LocalDateTime.now());
                streamingAccountMapper.insert(entity);
                successCount++;
            } catch (Exception e) {
                log.error("导入流媒体账号失败: {}", dto.getEmail(), e);
                errors.add(String.format("邮箱[%s]: 导入失败", dto.getEmail()));
            }
        }

        result.setSuccessCount(successCount);
        result.setSkipCount(skipCount);
        result.setFailCount(errors.size());
        result.setErrors(errors);
        log.info("批量导入流媒体账号完成 - 成功: {}, 跳过: {}, 失败: {}", successCount, skipCount, errors.size());
        return result;
    }

    @Override
    public StreamingAccount findById(String id) {
        StreamingAccount account = streamingAccountMapper.selectById(id);
        if (account != null) {
            dataSecurityUtil.validateMerchantAccess(account.getMerchantId(), "StreamingAccount");
        }
        return account;
    }

    @Override
    public StreamingAccount findByEmail(String email) {
        LambdaQueryWrapper<StreamingAccount> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(StreamingAccount::getEmail, email);
        return streamingAccountMapper.selectOne(wrapper);
    }

    @Override
    public StreamingAccount findByName(String name) {
        LambdaQueryWrapper<StreamingAccount> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(StreamingAccount::getName, name);
        return streamingAccountMapper.selectOne(wrapper);
    }

    @Override
    public IPage<StreamingAccount> findByMerchantId(String merchantId, StreamingAccountPageRequest request) {
        LambdaQueryWrapper<StreamingAccount> wrapper = new LambdaQueryWrapper<>();
        if (merchantId != null) {
            wrapper.eq(StreamingAccount::getMerchantId, merchantId);
        }
        wrapper.orderByDesc(StreamingAccount::getCreatedTime);
        IPage<StreamingAccount> page = new Page<>(request.getPageNum(), request.getPageSize(), true);
        return streamingAccountMapper.selectPage(page, wrapper);
    }

    @Override
    public List<StreamingAccount> findAllByMerchantId(String merchantId) {
        LambdaQueryWrapper<StreamingAccount> wrapper = new LambdaQueryWrapper<>();
        if (merchantId != null) {
            wrapper.eq(StreamingAccount::getMerchantId, merchantId);
        }
        wrapper.orderByDesc(StreamingAccount::getCreatedTime);
        return streamingAccountMapper.selectList(wrapper);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void update(String id, String name, String authCode) {
        StreamingAccount account = streamingAccountMapper.selectById(id);
        if (account == null) {
            throw new BusinessException(ResultCode.StreamingAccount.NOT_FOUND);
        }

        // 校验商户是否有效
        merchantService.validateMerchantActive(account.getMerchantId());

        if (name != null) {
            account.setName(name);
        }
        if (authCode != null) {
            account.setAuthCode(authCode);
        }

        streamingAccountMapper.updateById(account);
        log.info("更新流媒体账号 - ID: {}", id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void update(String id, String merchantId, String name, String authCode) {
        StreamingAccount account = streamingAccountMapper.selectById(id);
        if (account == null) {
            throw new BusinessException(ResultCode.StreamingAccount.NOT_FOUND);
        }

        if (merchantId != null) {
            merchantService.validateMerchantActive(merchantId);
            account.setMerchantId(merchantId);
        }
        if (name != null) {
            account.setName(name);
        }
        if (authCode != null) {
            account.setAuthCode(authCode);
        }

        streamingAccountMapper.updateById(account);
        log.info("更新流媒体账号 - ID: {}", id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateWithPassword(String id, String name, String password, String authCode) {
        StreamingAccount account = streamingAccountMapper.selectById(id);
        if (account == null) {
            throw new BusinessException(ResultCode.StreamingAccount.NOT_FOUND);
        }

        merchantService.validateMerchantActive(account.getMerchantId());

        if (name != null) {
            account.setName(name);
        }
        if (password != null) {
            account.setPasswordEncrypted(aesUtil.encrypt(password));
        }
        if (authCode != null) {
            account.setAuthCode(authCode);
        }

        streamingAccountMapper.updateById(account);
        log.info("更新流媒体账号（含密码）- ID: {}", id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateWithPassword(String id, String merchantId, String name, String password, String authCode) {
        updateWithPassword(id, merchantId, name, null, password, authCode, null);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateWithPassword(String id, String merchantId, String name, String email, String password, String authCode, String platform) {
        StreamingAccount account = streamingAccountMapper.selectById(id);
        if (account == null) {
            throw new BusinessException(ResultCode.StreamingAccount.NOT_FOUND);
        }

        if (merchantId != null) {
            merchantService.validateMerchantActive(merchantId);
            account.setMerchantId(merchantId);
        }
        if (name != null) {
            account.setName(name);
        }
        if (email != null) {
            // 检查邮箱是否与其他账号重复
            StreamingAccount existingByEmail = findByEmail(email);
            if (existingByEmail != null && !existingByEmail.getId().equals(id)) {
                throw new BusinessException(ResultCode.StreamingAccount.EMAIL_DUPLICATE);
            }
            account.setEmail(email);
        }
        if (password != null) {
            account.setPasswordEncrypted(aesUtil.encrypt(password));
        }
        if (authCode != null) {
            account.setAuthCode(authCode);
        }
        if (platform != null && !platform.isBlank()) {
            account.setPlatform(PlatformTypeUtil.requireValid(platform));
        }

        streamingAccountMapper.updateById(account);
        log.info("更新流媒体账号（含密码，管理员）- ID: {}", id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateStatus(String id, String status) {
        StreamingAccount account = streamingAccountMapper.selectById(id);
        if (account == null) {
            throw new BusinessException(ResultCode.StreamingAccount.NOT_FOUND);
        }

        if (!isValidStatus(status)) {
            throw new BusinessException(ResultCode.StreamingAccount.STATUS_INVALID);
        }

        account.setStatus(status);
        streamingAccountMapper.updateById(account);
        log.info("更新流媒体账号状态 - ID: {}, 新状态: {}", id, status);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateError(String id, String errorCode, String errorMessage) {
        StreamingAccount account = streamingAccountMapper.selectById(id);
        if (account == null) {
            throw new BusinessException(ResultCode.StreamingAccount.NOT_FOUND);
        }

        account.setStatus("error");
        account.setLastErrorCode(errorCode);
        account.setLastErrorMessage(errorMessage);
        account.setLastErrorTime(LocalDateTime.now());
        account.setErrorRetryCount(account.getErrorRetryCount() == null ? 1 : account.getErrorRetryCount() + 1);

        streamingAccountMapper.updateById(account);
        log.warn("流媒体账号错误 - ID: {}, 错误码: {}, 错误信息: {}", id, errorCode, errorMessage);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateHeartbeat(String id) {
        StreamingAccount account = streamingAccountMapper.selectById(id);
        if (account == null) {
            throw new BusinessException(ResultCode.StreamingAccount.NOT_FOUND);
        }

        account.setLastHeartbeat(LocalDateTime.now());
        streamingAccountMapper.updateById(account);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void delete(String id) {
        StreamingAccount account = streamingAccountMapper.selectById(id);
        if (account == null) {
            throw new BusinessException(ResultCode.StreamingAccount.NOT_FOUND);
        }

        streamingAccountMapper.deleteById(id);
        log.info("删除流媒体账号 - ID: {}", id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateAgentId(String id, String agentId) {
        StreamingAccount account = streamingAccountMapper.selectById(id);
        if (account == null) {
            throw new BusinessException(ResultCode.StreamingAccount.NOT_FOUND);
        }

        account.setAgentId(agentId);
        streamingAccountMapper.updateById(account);
        log.info("更新流媒体账号Agent绑定 - ID: {}, AgentID: {}", id, agentId);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateTaskStatus(String id, String taskStatus) {
        StreamingAccount account = streamingAccountMapper.selectById(id);
        if (account == null) {
            throw new BusinessException(ResultCode.StreamingAccount.NOT_FOUND);
        }

        account.setTaskStatus(taskStatus);
        
        // 状态变为空闲时，自动重置运行Agent
        if ("idle".equalsIgnoreCase(taskStatus) && account.getAgentId() != null) {
            account.setAgentId(null);
            log.info("流媒体账号状态为空闲，自动重置运行Agent - ID: {}", id);
        }
        
        streamingAccountMapper.updateById(account);
        log.info("更新流媒体账号任务状态 - ID: {}, 任务状态: {}", id, taskStatus);
    }

    @Override
    public boolean isAgentOnline(String id) {
        StreamingAccount account = streamingAccountMapper.selectById(id);
        if (account == null || account.getAgentId() == null) {
            return false;
        }
        return com.bend.platform.websocket.AgentWebSocketEndpoint.isAgentOnline(account.getAgentId());
    }

    @Override
    public void clearAgentBindingByAgentId(String agentId) {
        if (agentId == null || agentId.isEmpty()) {
            return;
        }

        // 查找该Agent关联的所有流媒体账号
        List<StreamingAccount> accounts = streamingAccountMapper.selectList(
            new LambdaQueryWrapper<StreamingAccount>()
                .eq(StreamingAccount::getAgentId, agentId)
        );

        if (accounts == null || accounts.isEmpty()) {
            log.debug("没有找到Agent关联的流媒体账号 - AgentID: {}", agentId);
            return;
        }

        // 清空每个账号的agentId和任务状态
        for (StreamingAccount account : accounts) {
            account.setAgentId(null);
            account.setTaskStatus("idle");
            streamingAccountMapper.updateById(account);
            log.info("清空流媒体账号Agent绑定 - AccountID: {}, Email: {}", account.getId(), account.getEmail());
        }

        log.info("清空Agent关联的流媒体账号绑定完成 - AgentID: {}, 账号数量: {}", agentId, accounts.size());
    }

    private boolean isValidStatus(String status) {
        return "idle".equals(status) || "busy".equals(status) || "error".equals(status);
    }
}