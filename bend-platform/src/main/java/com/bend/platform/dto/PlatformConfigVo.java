package com.bend.platform.dto;

import lombok.Data;

/**
 * 平台部署模式配置（供前端区分总控/分控 UI）。
 */
@Data
public class PlatformConfigVo {

    /** 部署模式：master=总控 / tenant=分控 */
    private String mode;
}
