package com.bend.platform.service;

import com.bend.platform.entity.Task;
import java.util.List;
import java.util.concurrent.CompletableFuture;

public interface TaskExecutorService {

    CompletableFuture<Void> executeTaskAsync(Task task);

    void executeTask(Task task);

    void cancelTask(String taskId);
}
