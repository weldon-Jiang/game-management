package com.bend.platform.dto;

import lombok.Data;
import java.time.LocalDateTime;

/**
 * 流媒体账号编辑详情DTO
 */
@Data
public class StreamingAccountEditDto {
    private String id;
    private String merchantId;
    private String name;
    private String email;
    private String status;
    private String authCode;
    private boolean passwordSet;
    private LocalDateTime createdTime;
}
