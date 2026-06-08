package com.bend.platform.dto;

import lombok.Data;

/**
 * 任务暂停请求：mode=immediate 立即暂停，after_match 当前比赛结束后暂停。
 */
@Data
public class TaskPauseRequest {
    /** immediate | after_match */
    private String mode = "immediate";
}
