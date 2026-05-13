package com.bend.platform.service;

import com.bend.platform.entity.TaskGameAccountStatus;
import java.util.List;

public interface TaskGameAccountStatusService {

    void createStatusRecords(String taskId, List<String> gameAccountIds, String streamingAccountId);

    List<TaskGameAccountStatus> findByTaskId(String taskId);

    TaskGameAccountStatus findByTaskIdAndGameAccountId(String taskId, String gameAccountId);

    void updateMatchComplete(String taskId, String gameAccountId, boolean success);

    void updateStatus(String taskId, String gameAccountId, String status);

    boolean areAllGameAccountsCompleted(String taskId);

    int getCompletedCount(String taskId);

    int getTotalCount(String taskId);
}
