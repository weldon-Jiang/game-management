package com.bend.platform.service;

import com.bend.platform.entity.TaskEvent;

import java.util.List;

public interface TaskEventService {

    List<TaskEvent> listByTaskId(String taskId, int limit);

    List<TaskEvent> listByTaskIdForMerchant(String taskId, String merchantId, int limit);
}
