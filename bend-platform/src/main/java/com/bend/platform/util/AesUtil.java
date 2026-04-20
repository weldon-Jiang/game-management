package com.bend.platform.util;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.Cipher;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;

/**
 * AES加密工具类
 * 使用AES-128/192/256-ECB模式，ZeroPadding填充
 */
@Component
public class AesUtil {

    @Value("${aes.secret}")
    private String secret;

    /**
     * 获取AES密钥
     * 密钥长度不足16字节时补0，超过16字节则截断
     */
    private SecretKeySpec getKeySpec() {
        byte[] keyBytes = secret.getBytes(StandardCharsets.UTF_8);
        int keyLen = keyBytes.length;
        if (keyLen < 16) {
            byte[] padded = new byte[16];
            System.arraycopy(keyBytes, 0, padded, 0, keyLen);
            keyBytes = padded;
            keyLen = 16;
        }
        return new SecretKeySpec(keyBytes, "AES");
    }

    /**
     * 获取AES算法名称
     * 使用AES/ECB/NoPadding模式
     */
    private String getAlgorithm() {
        return "AES/ECB/NoPadding";
    }

    /**
     * ZeroPadding填充
     * 数据长度不是16的倍数时，在末尾添加0x00直到满足16字节
     */
    private byte[] zeroPad(byte[] data) {
        int remainder = data.length % 16;
        if (remainder == 0) {
            return data;
        }
        int padLen = 16 - remainder;
        byte[] padded = new byte[data.length + padLen];
        System.arraycopy(data, 0, padded, 0, data.length);
        return padded;
    }

    /**
     * 移除ZeroPadding
     * 移除末尾的0x00
     */
    private byte[] zeroUnpad(byte[] data) {
        int i = data.length - 1;
        while (i >= 0 && data[i] == 0) {
            i--;
        }
        return java.util.Arrays.copyOf(data, i + 1);
    }

    /**
     * AES加密
     *
     * @param plainText 明文字符串
     * @return 十六进制加密字符串
     */
    public String encrypt(String plainText) {
        try {
            SecretKeySpec keySpec = getKeySpec();
            Cipher cipher = Cipher.getInstance(getAlgorithm());
            cipher.init(Cipher.ENCRYPT_MODE, keySpec);
            byte[] padded = zeroPad(plainText.getBytes(StandardCharsets.UTF_8));
            byte[] encrypted = cipher.doFinal(padded);
            return bytesToHex(encrypted);
        } catch (Exception e) {
            throw new RuntimeException("AES加密失败", e);
        }
    }

    /**
     * AES解密
     *
     * @param encryptedText 十六进制加密字符串
     * @return 明文字符串
     */
    public String decrypt(String encryptedText) {
        try {
            SecretKeySpec keySpec = getKeySpec();
            Cipher cipher = Cipher.getInstance(getAlgorithm());
            cipher.init(Cipher.DECRYPT_MODE, keySpec);
            byte[] decrypted = cipher.doFinal(hexToBytes(encryptedText));
            byte[] unpadded = zeroUnpad(decrypted);
            String result = new String(unpadded, StandardCharsets.UTF_8);
            return result;
        } catch (Exception e) {
            throw new RuntimeException("AES解密失败: " + e.getMessage(), e);
        }
    }

    /**
     * 字节数组转十六进制字符串
     */
    private String bytesToHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder();
        for (byte b : bytes) {
            sb.append(String.format("%02x", b));
        }
        return sb.toString();
    }

    /**
     * 十六进制字符串转字节数组
     */
    private byte[] hexToBytes(String hex) {
        byte[] bytes = new byte[hex.length() / 2];
        for (int i = 0; i < bytes.length; i++) {
            bytes[i] = (byte) Integer.parseInt(hex.substring(i * 2, i * 2 + 2), 16);
        }
        return bytes;
    }
}