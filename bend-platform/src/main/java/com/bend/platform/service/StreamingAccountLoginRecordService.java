package com.bend.platform.service;

import com.bend.platform.entity.StreamingAccountLoginRecord;
import java.util.List;

/**
 * 流媒体账号Xbox登录记录服务接口
 */
public interface StreamingAccountLoginRecordService {

    /**
     * 记录流媒体账号在Xbox主机上的登录
     *
     * @param streamingAccountId 流媒体账号ID
     * @param xboxHostId        Xbox主机ID
     * @param gamertag          登录时使用的Gamertag
     */
    void recordLogin(String streamingAccountId, String xboxHostId, String gamertag);

    /**
     * 检查流媒体账号是否在该Xbox主机上登录过
     *
     * @param streamingAccountId 流媒体账号ID
     * @param xboxHostId        Xbox主机ID
     * @return 是否登录过
     */
    boolean hasLoggedIn(String streamingAccountId, String xboxHostId);

    /**
     * 获取流媒体账号登录过的所有Xbox主机
     *
     * @param streamingAccountId 流媒体账号ID
     * @return 登录记录列表
     */
    List<StreamingAccountLoginRecord> findByStreamingAccountId(String streamingAccountId);

    /**
     * 获取Xbox主机上登录过的所有流媒体账号
     *
     * @param xboxHostId Xbox主机ID
     * @return 登录记录列表
     */
    List<StreamingAccountLoginRecord> findByXboxHostId(String xboxHostId);

    /**
     * 删除流媒体账号在某个Xbox主机上的登录记录
     *
     * @param streamingAccountId 流媒体账号ID
     * @param xboxHostId        Xbox主机ID
     */
    void deleteRecord(String streamingAccountId, String xboxHostId);
}