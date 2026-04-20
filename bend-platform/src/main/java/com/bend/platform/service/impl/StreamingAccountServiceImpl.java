package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.dto.StreamingAccountPageRequest;
import com.bend.platform.entity.StreamingAccount;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.StreamingAccountMapper;
import com.bend.platform.service.MerchantService;
import com.bend.platform.service.StreamingAccountService;
import com.bend.platform.util.AesUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

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

    @Override
    @Transactional(rollbackFor = Exception.class)
    public StreamingAccount create(String merchantId, String name, String email, String password, String authCode) {
        // 校验商户是否有效
        merchantService.validateMerchantActive(merchantId);

        // 检查邮箱是否已被使用
        if (findByEmail(email) != null) {
            throw new BusinessException(ResultCode.StreamingAccount.EMAIL_DUPLICATE);
        }

        StreamingAccount account = new StreamingAccount();
        account.setMerchantId(merchantId);
        account.setName(name);
        account.setEmail(email);
        account.setPasswordEncrypted(aesUtil.encrypt(password));
        account.setAuthCode(authCode);
        account.setStatus("idle");

        streamingAccountMapper.insert(account);
        log.info("创建流媒体账号成功 - ID: {}, 邮箱: {}", account.getId(), email);
        return account;
    }

    @Override
    public StreamingAccount findById(String id) {
        return streamingAccountMapper.selectById(id);
    }

    @Override
    public StreamingAccount findByEmail(String email) {
        LambdaQueryWrapper<StreamingAccount> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(StreamingAccount::getEmail, email);
        return streamingAccountMapper.selectOne(wrapper);
    }

    @Override
    public IPage<StreamingAccount> findByMerchantId(String merchantId, StreamingAccountPageRequest request) {
        LambdaQueryWrapper<StreamingAccount> wrapper = new LambdaQueryWrapper<>();
        if (merchantId != null) {
            wrapper.eq(StreamingAccount::getMerchantId, merchantId);
        }
        wrapper.orderByDesc(StreamingAccount::getCreatedAt);
        Page<StreamingAccount> page = new Page<>(request.getPageNum(), request.getPageSize());
        return streamingAccountMapper.selectPage(page, wrapper);
    }

    @Override
    public List<StreamingAccount> findAllByMerchantId(String merchantId) {
        LambdaQueryWrapper<StreamingAccount> wrapper = new LambdaQueryWrapper<>();
        if (merchantId != null) {
            wrapper.eq(StreamingAccount::getMerchantId, merchantId);
        }
        wrapper.orderByDesc(StreamingAccount::getCreatedAt);
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
        account.setLastErrorAt(LocalDateTime.now());
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
        if (agentId != null) {
            account.setStatus("busy");
        } else {
            account.setStatus("idle");
        }
        streamingAccountMapper.updateById(account);
        log.info("更新流媒体账号Agent绑定 - ID: {}, AgentID: {}", id, agentId);
    }

    @Override
    public boolean isAgentOnline(String id) {
        StreamingAccount account = streamingAccountMapper.selectById(id);
        if (account == null || account.getAgentId() == null) {
            return false;
        }
        return com.bend.platform.websocket.AgentWebSocketEndpoint.isAgentOnline(account.getAgentId());
    }

    private boolean isValidStatus(String status) {
        return "idle".equals(status) || "busy".equals(status) || "error".equals(status);
    }
}