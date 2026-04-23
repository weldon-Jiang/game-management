package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bend.platform.entity.StreamingAccountLoginRecord;
import com.bend.platform.repository.StreamingAccountLoginRecordMapper;
import com.bend.platform.service.StreamingAccountLoginRecordService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 流媒体账号Xbox登录记录服务实现类
 *
 * 功能说明：
 * - 记录流媒体账号登录Xbox主机的时间和状态
 * - 提供登录记录的查询和管理
 *
 * 主要功能：
 * - 创建登录记录
 * - 根据流媒体账号ID查询登录记录
 * - 删除登录记录
 *
 * 依赖注入：
 * - 使用Lombok的@RequiredArgsConstructor注解
 * - 为所有 final字段生成构造器进行依赖注入
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class StreamingAccountLoginRecordServiceImpl implements StreamingAccountLoginRecordService {

    private final StreamingAccountLoginRecordMapper loginRecordMapper;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void recordLogin(String streamingAccountId, String xboxHostId, String gamertag) {
        LambdaQueryWrapper<StreamingAccountLoginRecord> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(StreamingAccountLoginRecord::getStreamingAccountId, streamingAccountId)
               .eq(StreamingAccountLoginRecord::getXboxHostId, xboxHostId);

        StreamingAccountLoginRecord record = loginRecordMapper.selectOne(wrapper);

        if (record == null) {
            record = new StreamingAccountLoginRecord();
            record.setStreamingAccountId(streamingAccountId);
            record.setXboxHostId(xboxHostId);
            record.setLoggedGamertag(gamertag);
            record.setLoggedTime(LocalDateTime.now());
            record.setUseCount(1);
            loginRecordMapper.insert(record);
            log.info("记录流媒体账号登录 - StreamingAccountID: {}, XboxHostID: {}, Gamertag: {}",
                    streamingAccountId, xboxHostId, gamertag);
        } else {
            record.setLoggedGamertag(gamertag);
            record.setLastUsedTime(LocalDateTime.now());
            record.setUseCount(record.getUseCount() == null ? 1 : record.getUseCount() + 1);
            loginRecordMapper.updateById(record);
            log.info("更新流媒体账号登录记录 - StreamingAccountID: {}, XboxHostID: {}, 使用次数: {}",
                    streamingAccountId, xboxHostId, record.getUseCount());
        }
    }

    @Override
    public boolean hasLoggedIn(String streamingAccountId, String xboxHostId) {
        LambdaQueryWrapper<StreamingAccountLoginRecord> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(StreamingAccountLoginRecord::getStreamingAccountId, streamingAccountId)
               .eq(StreamingAccountLoginRecord::getXboxHostId, xboxHostId);
        return loginRecordMapper.selectCount(wrapper) > 0;
    }

    @Override
    public List<StreamingAccountLoginRecord> findByStreamingAccountId(String streamingAccountId) {
        LambdaQueryWrapper<StreamingAccountLoginRecord> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(StreamingAccountLoginRecord::getStreamingAccountId, streamingAccountId)
               .orderByDesc(StreamingAccountLoginRecord::getLastUsedTime);
        return loginRecordMapper.selectList(wrapper);
    }

    @Override
    public List<StreamingAccountLoginRecord> findByXboxHostId(String xboxHostId) {
        LambdaQueryWrapper<StreamingAccountLoginRecord> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(StreamingAccountLoginRecord::getXboxHostId, xboxHostId)
               .orderByDesc(StreamingAccountLoginRecord::getLastUsedTime);
        return loginRecordMapper.selectList(wrapper);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void deleteRecord(String streamingAccountId, String xboxHostId) {
        LambdaQueryWrapper<StreamingAccountLoginRecord> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(StreamingAccountLoginRecord::getStreamingAccountId, streamingAccountId)
               .eq(StreamingAccountLoginRecord::getXboxHostId, xboxHostId);
        loginRecordMapper.delete(wrapper);
        log.info("删除流媒体账号登录记录 - StreamingAccountID: {}, XboxHostID: {}", streamingAccountId, xboxHostId);
    }
}