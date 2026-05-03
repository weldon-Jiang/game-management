package com.bend.platform.util;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;
import java.util.HashMap;
import java.util.Map;

/**
 * JWT工具类
 * 用于生成和解析JWT token
 */
@Slf4j
@Component
public class JwtUtil {

    @Value("${jwt.secret}")
    private String secret;

    @Value("${jwt.expiration}")
    private Long expiration;

    private static final long MILLIS_PER_SECOND = 1000;
    private static final long REFRESH_THRESHOLD_SECONDS = 3600;

    private SecretKey getSigningKey() {
        byte[] keyBytes = secret.getBytes(StandardCharsets.UTF_8);
        if (keyBytes.length < 32) {
            throw new IllegalStateException("JWT secret must be at least 32 characters for HS256");
        }
        return Keys.hmacShaKeyFor(keyBytes);
    }

    public String generateToken(String userId, String username, String merchantId, String role) {
        Map<String, Object> claims = new HashMap<>();
        claims.put("userId", userId);
        claims.put("merchantId", merchantId);
        claims.put("role", role);

        Date now = new Date();
        Date expiryDate = new Date(now.getTime() + expiration);

        return Jwts.builder()
                .claims(claims)
                .subject(username)
                .issuedAt(now)
                .expiration(expiryDate)
                .signWith(getSigningKey())
                .compact();
    }

    public Claims parseToken(String token) {
        return Jwts.parser()
                .verifyWith(getSigningKey())
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }

    public boolean validateToken(String token) {
        try {
            parseToken(token);
            return true;
        } catch (ExpiredJwtException e) {
            log.warn("JWT已过期: {}", e.getMessage());
            return false;
        } catch (JwtException e) {
            log.warn("JWT验证失败: {}", e.getMessage());
            return false;
        }
    }

    public boolean isTokenExpired(String token) {
        try {
            Claims claims = parseToken(token);
            return claims.getExpiration().before(new Date());
        } catch (ExpiredJwtException e) {
            return true;
        } catch (JwtException e) {
            log.warn("JWT解析失败: {}", e.getMessage());
            return true;
        }
    }

    public long getRemainingTimeSeconds(String token) {
        try {
            Claims claims = parseToken(token);
            Date expiration = claims.getExpiration();
            long remainingMillis = expiration.getTime() - System.currentTimeMillis();
            return Math.max(0, remainingMillis / MILLIS_PER_SECOND);
        } catch (JwtException e) {
            log.warn("JWT解析失败: {}", e.getMessage());
            return 0;
        }
    }

    public boolean needsRefresh(String token) {
        return getRemainingTimeSeconds(token) < REFRESH_THRESHOLD_SECONDS;
    }

    public String getUserIdFromToken(String token) {
        Claims claims = parseToken(token);
        return claims.get("userId", String.class);
    }

    public String getUsernameFromToken(String token) {
        return parseToken(token).getSubject();
    }

    public String getMerchantIdFromToken(String token) {
        Claims claims = parseToken(token);
        return claims.get("merchantId", String.class);
    }

    public String getRoleFromToken(String token) {
        Claims claims = parseToken(token);
        return claims.get("role", String.class);
    }

    public String refreshToken(String token) {
        Claims claims = parseToken(token);
        String userId = claims.get("userId", String.class);
        String merchantId = claims.get("merchantId", String.class);
        String role = claims.get("role", String.class);
        String username = claims.getSubject();
        return generateToken(userId, username, merchantId, role);
    }
}
