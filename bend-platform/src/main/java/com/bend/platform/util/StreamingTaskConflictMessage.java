package com.bend.platform.util;

import com.bend.platform.entity.Task;
import org.springframework.util.StringUtils;

/**
 * User-facing message when a streaming account already has an active task.
 */
public final class StreamingTaskConflictMessage {

    private StreamingTaskConflictMessage() {
    }

    public static String format(Task activeTask, String agentDisplayName) {
        String agentLabel = StringUtils.hasText(agentDisplayName)
                ? agentDisplayName
                : (activeTask != null && StringUtils.hasText(activeTask.getTargetAgentId())
                        ? activeTask.getTargetAgentId()
                        : null);
        String base = StringUtils.hasText(agentLabel)
                ? String.format("该串流账号正在 Agent「%s」上运行任务", agentLabel)
                : "该串流账号正在运行任务";
        return base + "，请等待任务完成，或在任务详情中终止任务后再启动";
    }
}
