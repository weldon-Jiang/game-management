package com.bend.platform.service;

import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

/**
 * 将 WebSocket 下发推迟到当前事务提交之后，避免 Agent 已收指令而 DB 回滚的不一致。
 */
@Service
public class TaskWsDispatchService {

    /**
     * 若处于事务中则 afterCommit 执行；否则立即执行。
     */
    public void dispatchAfterCommit(Runnable action) {
        if (TransactionSynchronizationManager.isSynchronizationActive()) {
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override
                public void afterCommit() {
                    action.run();
                }
            });
        } else {
            action.run();
        }
    }
}
