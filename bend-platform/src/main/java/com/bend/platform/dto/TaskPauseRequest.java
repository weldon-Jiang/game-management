package com.bend.platform.dto;

import lombok.Data;

@Data
public class TaskPauseRequest {
    /** immediate | after_match */
    private String mode = "immediate";
}
