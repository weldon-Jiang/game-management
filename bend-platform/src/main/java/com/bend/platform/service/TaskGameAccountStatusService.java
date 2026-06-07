package com.bend.platform.service;

import com.bend.platform.entity.TaskGameAccountStatus;

import java.util.List;

public interface TaskGameAccountStatusService {

    void createStatusRecords(String taskId, List<String> gameAccountIds, List<Integer> dailyLimits,
                             String streamingAccountId, String sessionId);

    List<TaskGameAccountStatus> findByTaskId(String taskId);

    TaskGameAccountStatus findByTaskIdAndGameAccountId(String taskId, String gameAccountId);

    void updateMatchComplete(String taskId, String gameAccountId, boolean success);

    void updateStatus(String taskId, String gameAccountId, String status);

    void updateToGamePreparing(String taskId, String gameAccountId);

    void updateToGaming(String taskId, String gameAccountId);

    void updateToTimeout(String taskId, String gameAccountId);



    boolean areAllGameAccountsCompleted(String taskId);

    int getCompletedCount(String taskId);

    int getTotalCount(String taskId);

    void cancelByTaskId(String taskId);

    void updateDailyMatchInfo(String taskId, String gameAccountId, Integer todayCompleted, Integer dailyLimit);

    void updateProvisioningStatus(TaskGameAccountStatus status);
}
