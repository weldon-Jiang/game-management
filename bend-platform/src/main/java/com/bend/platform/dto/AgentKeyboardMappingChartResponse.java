package com.bend.platform.dto;

import lombok.Builder;
import lombok.Data;

import java.util.List;

/**
 * Agent F8 人工接管键盘映射图（只读展示，含 Agent 扩展键位）。
 */
@Data
@Builder
public class AgentKeyboardMappingChartResponse {

    /** 是否使用平台默认 12 项（DB 为 NULL） */
    private boolean usingDefault;

    /** 按类别分组的对照表 */
    private List<ChartGroup> groups;

    /** 键盘可视化：每个已映射键在图上的标注 */
    private List<KeyCap> keyCaps;

    /** F8 调试热键（非手柄映射） */
    private List<DebugHotkey> debugHotkeys;

    @Data
    @Builder
    public static class ChartGroup {
        private String category;
        private String label;
        /** 是否可在「键盘映射」弹窗中自定义 */
        private boolean customizable;
        private List<ChartItem> items;
    }

    @Data
    @Builder
    public static class ChartItem {
        /** 展示用键名，如 W、Shift、↑ */
        private String keys;
        /** 手柄目标，如 左摇杆 ↑ */
        private String target;
    }

    @Data
    @Builder
    public static class KeyCap {
        /** pygame 键名（小写），供前端定位键位 */
        private String bindingKey;
        /** 键帽显示文字 */
        private String displayKey;
        /** 手柄映射说明 */
        private String targetLabel;
        /** 分类：left_stick / dpad / face / shoulder / trigger / right_stick / stick_click / system */
        private String category;
    }

    @Data
    @Builder
    public static class DebugHotkey {
        private String key;
        private String description;
    }
}
