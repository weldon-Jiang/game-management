package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.dto.GameAccountPageRequest;
import com.bend.platform.entity.GameAccount;
import com.bend.platform.entity.StreamingAccount;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.GameAccountMapper;
import com.bend.platform.repository.StreamingAccountMapper;
import com.bend.platform.service.GameAccountService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.CollectionUtils;

import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.Collectors;

/**
 * 游戏账号服务实现类
 *
 * 功能说明：
 * - 管理Xbox游戏账号的CRUD操作
 * - 游戏账号关联到流媒体账号
 *
 * 主要功能：
 * - 创建游戏账号
 * - 分页查询游戏账号
 * - 根据流媒体账号ID查询游戏账号
 * - 更新游戏账号信息
 * - 删除游戏账号
 * - 批量更新游戏账号的AgentID
 *
 * 依赖注入：
 * - 使用Lombok的@RequiredArgsConstructor注解
 * - 为所有 final字段生成构造器进行依赖注入
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class GameAccountServiceImpl implements GameAccountService {

    private final GameAccountMapper gameAccountMapper;
    private final StreamingAccountMapper streamingAccountMapper;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public GameAccount create(String merchantId, GameAccount account) {
        StreamingAccount streaming = streamingAccountMapper.selectById(account.getStreamingId());
        if (streaming == null) {
            throw new BusinessException(ResultCode.StreamingAccount.NOT_FOUND);
        }
        if (!streaming.getMerchantId().equals(merchantId)) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        GameAccount entity = new GameAccount();
        entity.setStreamingId(account.getStreamingId());
        entity.setName(account.getName());
        entity.setXboxGamertag(account.getXboxGamertag());
        entity.setXboxLiveEmail(account.getXboxLiveEmail());
        entity.setXboxLivePasswordEncrypted(account.getXboxLivePasswordEncrypted());
        entity.setIsActive(true);
        entity.setIsPrimary(false);
        entity.setCreatedTime(LocalDateTime.now());
        entity.setUpdatedTime(LocalDateTime.now());

        gameAccountMapper.insert(entity);
        log.info("创建游戏账号成功 - ID: {}, 名称: {}", entity.getId(), entity.getName());
        return entity;
    }

    @Override
    public GameAccount findById(String id) {
        return gameAccountMapper.selectById(id);
    }

    @Override
    public GameAccount findByGamertag(String gamertag) {
        LambdaQueryWrapper<GameAccount> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(GameAccount::getXboxGamertag, gamertag);
        return gameAccountMapper.selectOne(wrapper);
    }

    @Override
    public IPage<GameAccount> findByMerchantId(String merchantId, GameAccountPageRequest request) {
        LambdaQueryWrapper<StreamingAccount> streamingWrapper = new LambdaQueryWrapper<>();
        streamingWrapper.eq(StreamingAccount::getMerchantId, merchantId);
        List<StreamingAccount> streamingAccounts = streamingAccountMapper.selectList(streamingWrapper);
        if (CollectionUtils.isEmpty(streamingAccounts)) {
            return new Page<>(request.getPageNum(), request.getPageSize());
        }
        List<String> streamingIds = streamingAccounts.stream()
                .map(StreamingAccount::getId)
                .collect(Collectors.toList());

        LambdaQueryWrapper<GameAccount> wrapper = new LambdaQueryWrapper<>();
        wrapper.in(GameAccount::getStreamingId, streamingIds)
               .orderByDesc(GameAccount::getCreatedTime);
        Page<GameAccount> page = new Page<>(request.getPageNum(), request.getPageSize());
        return gameAccountMapper.selectPage(page, wrapper);
    }

    @Override
    public IPage<GameAccount> findByStreamingId(String streamingId, GameAccountPageRequest request) {
        LambdaQueryWrapper<GameAccount> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(GameAccount::getStreamingId, streamingId)
               .orderByDesc(GameAccount::getCreatedTime);
        Page<GameAccount> page = new Page<>(request.getPageNum(), request.getPageSize());
        return gameAccountMapper.selectPage(page, wrapper);
    }

    @Override
    public List<GameAccount> findAllByStreamingId(String streamingId) {
        LambdaQueryWrapper<GameAccount> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(GameAccount::getStreamingId, streamingId)
               .orderByDesc(GameAccount::getCreatedTime);
        return gameAccountMapper.selectList(wrapper);
    }

    @Override
    public IPage<GameAccount> findAll(GameAccountPageRequest request) {
        LambdaQueryWrapper<GameAccount> wrapper = new LambdaQueryWrapper<>();
        wrapper.orderByDesc(GameAccount::getCreatedTime);
        Page<GameAccount> page = new Page<>(request.getPageNum(), request.getPageSize());
        return gameAccountMapper.selectPage(page, wrapper);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void update(String id, GameAccount account) {
        GameAccount existing = gameAccountMapper.selectById(id);
        if (existing == null) {
            throw new BusinessException(ResultCode.GameAccount.NOT_FOUND);
        }

        if (account.getName() != null) {
            existing.setName(account.getName());
        }
        if (account.getXboxLiveEmail() != null) {
            existing.setXboxLiveEmail(account.getXboxLiveEmail());
        }
        if (account.getXboxLivePasswordEncrypted() != null) {
            existing.setXboxLivePasswordEncrypted(account.getXboxLivePasswordEncrypted());
        }
        if (account.getIsActive() != null) {
            existing.setIsActive(account.getIsActive());
        }
        existing.setUpdatedTime(LocalDateTime.now());

        gameAccountMapper.updateById(existing);
        log.info("更新游戏账号 - ID: {}", id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void lock(String id, String xboxHostId) {
        GameAccount account = gameAccountMapper.selectById(id);
        if (account == null) {
            throw new BusinessException(ResultCode.GameAccount.NOT_FOUND);
        }

        account.setIsActive(false);
        
        account.setUpdatedTime(LocalDateTime.now());

        gameAccountMapper.updateById(account);
        log.info("锁定游戏账号 - ID: {}, XboxHost: {}", id, xboxHostId);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void unlock(String id) {
        GameAccount account = gameAccountMapper.selectById(id);
        if (account == null) {
            throw new BusinessException(ResultCode.GameAccount.NOT_FOUND);
        }

        account.setIsActive(true);
        
        account.setUpdatedTime(LocalDateTime.now());

        gameAccountMapper.updateById(account);
        log.info("解锁游戏账号 - ID: {}", id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void setPrimary(String id, boolean primary) {
        GameAccount account = gameAccountMapper.selectById(id);
        if (account == null) {
            throw new BusinessException(ResultCode.GameAccount.NOT_FOUND);
        }

        account.setIsPrimary(primary);
        account.setUpdatedTime(LocalDateTime.now());

        gameAccountMapper.updateById(account);
        log.info("设置游戏账号为主账号 - ID: {}, Primary: {}", id, primary);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void delete(String id) {
        gameAccountMapper.deleteById(id);
        log.info("删除游戏账号 - ID: {}", id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateAgentId(String id, String agentId) {
        GameAccount account = gameAccountMapper.selectById(id);
        if (account == null) {
            throw new BusinessException(ResultCode.GameAccount.NOT_FOUND);
        }

        
        account.setUpdatedTime(LocalDateTime.now());
        gameAccountMapper.updateById(account);
        log.info("更新游戏账号Agent绑定 - ID: {}, AgentID: {}", id, agentId);
    }

    @Override
    public List<GameAccount> findByStreamingId(String streamingId) {
        LambdaQueryWrapper<GameAccount> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(GameAccount::getStreamingId, streamingId)
               .orderByDesc(GameAccount::getCreatedTime);
        return gameAccountMapper.selectList(wrapper);
    }
}