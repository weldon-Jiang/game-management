package com.bend.platform.util;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Base64;
import java.util.UUID;

/**
 * License 签名与密钥工具
 *
 * <p>用途:
 * <ul>
 *   <li>生成 license_key(对外可见的授权码)</li>
 *   <li>对 license_secret 做哈希存储(服务端校验)</li>
 *   <li>对校验结果做 HMAC-SHA256 签名(分控本地缓存防篡改)</li>
 * </ul>
 *
 * <p>签名密钥 license.sign-secret 由总控配置注入,分控包打包时同一密钥内嵌,
 * 因此分控可验签、但无法伪造(无法生成合法签名除非拿到密钥)。
 */
@Component
public class LicenseSignUtil {

    @Value("${license.sign-secret:}")
    private String signSecret;

    /** 生成对外可见的 license_key,形如 LIC-xxxxxxxx-xxxxxxxx-xxxxxxxx */
    public String generateLicenseKey() {
        String raw = UUID.randomUUID().toString().replace("-", "");
        return "LIC-" + raw.substring(0, 8) + "-" + raw.substring(8, 16) + "-" + raw.substring(16, 24);
    }

    /** 生成 license_secret(分控持有,用于证明自己是该 license 的合法持有者) */
    public String generateLicenseSecret() {
        return UUID.randomUUID().toString().replace("-", "") + UUID.randomUUID().toString().replace("-", "");
    }

    /** 对 license_secret 做 SHA-256 哈希存储(不存明文) */
    public String hashSecret(String licenseSecret) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] hash = md.digest(licenseSecret.getBytes(StandardCharsets.UTF_8));
            return bytesToHex(hash);
        } catch (Exception e) {
            throw new IllegalStateException("SHA-256 不可用", e);
        }
    }

    /** 校验传入的 license_secret 明文与存储的哈希是否匹配 */
    public boolean verifySecret(String plainSecret, String storedHash) {
        if (plainSecret == null || storedHash == null) {
            return false;
        }
        return storedHash.equalsIgnoreCase(hashSecret(plainSecret));
    }

    /**
     * 对校验结果 payload 做 HMAC-SHA256 签名。
     *
     * @param payload 签名前的原始 JSON 字符串
     * @return Base64 编码的签名
     */
    public String sign(String payload) {
        ensureSecret();
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            SecretKeySpec keySpec = new SecretKeySpec(signSecret.getBytes(StandardCharsets.UTF_8), "HmacSHA256");
            mac.init(keySpec);
            byte[] hmac = mac.doFinal(payload.getBytes(StandardCharsets.UTF_8));
            return Base64.getEncoder().encodeToString(hmac);
        } catch (Exception e) {
            throw new IllegalStateException("HMAC-SHA256 签名失败", e);
        }
    }

    /** 校验签名是否匹配 */
    public boolean verify(String payload, String signature) {
        if (signature == null) {
            return false;
        }
        return signature.equals(sign(payload));
    }

    private void ensureSecret() {
        if (signSecret == null || signSecret.length() < 32) {
            throw new IllegalStateException("license.sign-secret 未配置或长度不足32字符(HMAC-SHA256 要求)");
        }
    }

    private String bytesToHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder();
        for (byte b : bytes) {
            sb.append(String.format("%02x", b));
        }
        return sb.toString();
    }
}
