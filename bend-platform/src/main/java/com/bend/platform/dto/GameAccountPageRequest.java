package com.bend.platform.dto;

import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 游戏账号分页查询参数。
 */
@Data
@EqualsAndHashCode(callSuper = true)
public class GameAccountPageRequest extends PageRequest {
    private String streamingId;
}