package com.bend.platform.service;

import com.bend.platform.entity.StreamingSession;
import com.bend.platform.entity.Task;

public interface StreamingSessionService {

    StreamingSession createForTask(Task task, String merchantId);

    StreamingSession findByTaskId(String taskId);

    StreamingSession findById(String id);

    void updatePhase(String sessionId, String phase, String message);

    void lockGameAction(String sessionId, String gameActionType);

    void closeSession(String sessionId, String phase);
}
