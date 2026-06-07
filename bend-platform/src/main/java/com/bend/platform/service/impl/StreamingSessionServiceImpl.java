package com.bend.platform.service.impl;

import com.bend.platform.entity.StreamingSession;
import com.bend.platform.entity.Task;
import com.bend.platform.repository.StreamingSessionMapper;
import com.bend.platform.service.StreamingSessionService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;

@Service
@RequiredArgsConstructor
public class StreamingSessionServiceImpl implements StreamingSessionService {

    private final StreamingSessionMapper streamingSessionMapper;

    @Override
    public StreamingSession createForTask(Task task, String merchantId) {
        StreamingSession session = new StreamingSession();
        session.setTaskId(task.getId());
        session.setMerchantId(merchantId);
        session.setStreamingAccountId(task.getStreamingAccountId());
        session.setXboxHostId(task.getXboxHostId());
        session.setTargetAgentId(task.getTargetAgentId());
        session.setPhase("opening");
        session.setInputMode("virtual");
        session.setDecodeMode("auto");
        session.setStartedTime(LocalDateTime.now());
        streamingSessionMapper.insert(session);
        return session;
    }

    @Override
    public StreamingSession findByTaskId(String taskId) {
        return streamingSessionMapper.selectOne(
                new com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<StreamingSession>()
                        .eq(StreamingSession::getTaskId, taskId)
                        .last("LIMIT 1"));
    }

    @Override
    public StreamingSession findById(String id) {
        return streamingSessionMapper.selectById(id);
    }

    @Override
    public void updatePhase(String sessionId, String phase, String message) {
        StreamingSession session = streamingSessionMapper.selectById(sessionId);
        if (session == null) {
            return;
        }
        session.setPhase(phase);
        if ("ready".equals(phase)) {
            session.setReadyTime(LocalDateTime.now());
        }
        if (message != null && !message.isBlank()) {
            session.setErrorMessage(message);
        }
        streamingSessionMapper.updateById(session);
    }

    @Override
    public void lockGameAction(String sessionId, String gameActionType) {
        StreamingSession session = streamingSessionMapper.selectById(sessionId);
        if (session == null) {
            return;
        }
        session.setGameActionType(gameActionType);
        session.setGameActionLockedAt(LocalDateTime.now());
        session.setPhase("automating");
        streamingSessionMapper.updateById(session);
    }

    @Override
    public void closeSession(String sessionId, String phase) {
        StreamingSession session = streamingSessionMapper.selectById(sessionId);
        if (session == null) {
            return;
        }
        session.setPhase(phase);
        session.setClosedTime(LocalDateTime.now());
        streamingSessionMapper.updateById(session);
    }
}
