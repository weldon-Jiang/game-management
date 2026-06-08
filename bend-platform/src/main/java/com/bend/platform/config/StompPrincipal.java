package com.bend.platform.config;

import com.bend.platform.dto.LoginUserInfo;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

import java.security.Principal;

/**
 * STOMP 会话主体，承载 JWT 解析后的登录用户信息。
 */
@Getter
@RequiredArgsConstructor
public class StompPrincipal implements Principal {

    private final LoginUserInfo userInfo;

    @Override
    public String getName() {
        return userInfo != null ? userInfo.getUsername() : "anonymous";
    }
}
