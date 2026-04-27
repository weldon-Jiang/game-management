package com.bend.platform.dto;

import lombok.Data;
import lombok.EqualsAndHashCode;

@Data
@EqualsAndHashCode(callSuper = true)
public class GameAccountPageRequest extends PageRequest {
    private String streamingId;
}