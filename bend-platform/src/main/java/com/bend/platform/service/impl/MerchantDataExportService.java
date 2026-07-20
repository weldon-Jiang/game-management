package com.bend.platform.service.impl;

import com.bend.platform.config.MasterModeCondition;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Conditional;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.sql.Types;
import java.util.Arrays;
import java.util.List;

/**
 * 商户数据导出服务(总控侧)
 *
 * <p>打分控包时,把指定商户的全量私有数据导出为 SQL(INSERT IGNORE 语句),
 * 供分控包初始化时导入本地库,使商户在分控后台看到与总控一致的初始数据。
 *
 * <p>纯 JDBC 生成,不依赖 mysqldump,打包脚本只需调一个 HTTP 接口。
 * 全局配置表(merchant_group / agent_version)不导出,分控用 schema.sql 自带初始值。
 */
@Slf4j
@Service
@RequiredArgsConstructor
@Conditional(MasterModeCondition.class)
public class MerchantDataExportService {

    private final JdbcTemplate jdbcTemplate;

    /**
     * 要导出的表及过滤列(null=全表导出)。
     * merchant 表主键是 id,其余按 merchant_id 过滤。
     */
    private static final List<String[]> TABLES = Arrays.asList(
            new String[]{"merchant", "id"},
            new String[]{"merchant_user", "merchant_id"},
            new String[]{"merchant_balance", "merchant_id"},
            new String[]{"merchant_registration_code", "merchant_id"},
            new String[]{"subscription", "merchant_id"},
            new String[]{"activation_code", "merchant_id"},
            new String[]{"streaming_account", "merchant_id"},
            new String[]{"streaming_account_auth_cache", "merchant_id"},
            new String[]{"streaming_account_host_binding", "merchant_id"},
            new String[]{"game_account", "merchant_id"},
            new String[]{"xbox_host", "merchant_id"},
            new String[]{"agent_instance", "merchant_id"},
            new String[]{"task", "merchant_id"},
            new String[]{"task_event", "merchant_id"},
            new String[]{"streaming_session", "merchant_id"},
            new String[]{"automation_usage", "merchant_id"},
            new String[]{"automation_billing_event", "merchant_id"},
            new String[]{"point_transaction", "merchant_id"},
            new String[]{"device_binding", "merchant_id"},
            new String[]{"recharge_card", "merchant_id"},
            new String[]{"recharge_record", "merchant_id"},
            new String[]{"operation_log", "merchant_id"}
    );

    /**
     * 导出指定商户的全量数据为 SQL 文本。
     */
    public String export(String merchantId) {
        StringBuilder sb = new StringBuilder();
        sb.append("-- ================================================\n");
        sb.append("-- 分控商户数据导出 merchantId=").append(merchantId).append("\n");
        sb.append("-- 由总控 MerchantDataExportService 生成,导入分控本地库\n");
        sb.append("-- 全部使用 INSERT IGNORE,避免与 schema.sql 初始数据冲突\n");
        sb.append("-- ================================================\n");
        sb.append("SET NAMES utf8mb4;\n");
        sb.append("USE bend_platform;\n");

        for (String[] t : TABLES) {
            exportTable(sb, t[0], t[1], merchantId);
        }
        return sb.toString();
    }

    private void exportTable(StringBuilder sb, String table, String filterCol, String merchantId) {
        sb.append("\n-- ---------- ").append(table).append(" ----------\n");
        String sql = filterCol != null
                ? "SELECT * FROM `" + table + "` WHERE `" + filterCol + "` = ?"
                : "SELECT * FROM `" + table + "`";
        Object[] args = filterCol != null ? new Object[]{merchantId} : new Object[]{};

        int[] count = new int[1];
        jdbcTemplate.query(sql, args, rs -> {
            count[0]++;
            ResultSetMetaData meta = rs.getMetaData();
            int n = meta.getColumnCount();
            String[] cols = new String[n];
            for (int i = 0; i < n; i++) {
                cols[i] = meta.getColumnName(i + 1);
            }
            sb.append("INSERT IGNORE INTO `").append(table).append("` (");
            for (int i = 0; i < n; i++) {
                if (i > 0) sb.append(",");
                sb.append("`").append(cols[i]).append("`");
            }
            sb.append(") VALUES (");
            for (int i = 1; i <= n; i++) {
                if (i > 1) sb.append(",");
                sb.append(formatValue(rs, i, meta.getColumnType(i)));
            }
            sb.append(");\n");
        });
        if (count[0] == 0) {
            sb.append("-- (无数据)\n");
        }
    }

    private String formatValue(ResultSet rs, int i, int sqlType) {
        try {
            switch (sqlType) {
                case Types.INTEGER: case Types.BIGINT: case Types.SMALLINT: case Types.TINYINT:
                case Types.DECIMAL: case Types.NUMERIC: case Types.DOUBLE: case Types.FLOAT: case Types.REAL:
                    Object num = rs.getObject(i);
                    return num == null ? "NULL" : num.toString();
                case Types.BIT: case Types.BOOLEAN:
                    Object b = rs.getObject(i);
                    if (b == null) return "NULL";
                    if (b instanceof Boolean) return (Boolean) b ? "1" : "0";
                    return b.toString();
                case Types.BLOB: case Types.BINARY: case Types.VARBINARY: case Types.LONGVARBINARY:
                    byte[] bytes = rs.getBytes(i);
                    return bytes == null ? "NULL" : "0x" + bytesToHex(bytes);
                default:
                    // 字符串/日期/时间/JSON/TEXT 统一用 getString 转义加引号
                    String s = rs.getString(i);
                    return s == null ? "NULL" : "'" + escape(s) + "'";
            }
        } catch (Exception e) {
            try {
                String s = rs.getString(i);
                return s == null ? "NULL" : "'" + escape(s) + "'";
            } catch (Exception ex) {
                return "NULL";
            }
        }
    }

    private String escape(String s) {
        return s.replace("\\", "\\\\")
                .replace("'", "\\'")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\0", "\\0");
    }

    private String bytesToHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) {
            sb.append(String.format("%02x", b));
        }
        return sb.toString();
    }
}
