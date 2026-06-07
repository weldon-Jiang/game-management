package com.bend.platform.enums;

/**
 * Step4 game automation action type (sent to Agent as gameActionType).
 *
 * @see TaskType Agent WebSocket task routing channel (stream_control, etc.)
 */
public enum GameActionType {

    AUCTION_TRANSFER("auction_transfer", "拍卖行转会", true),
    SQUAD_BATTLE("squad_battle", "SQB模式", true),
    TRANSFER_SQB_COMBO("transfer_sqb_combo", "转会+SQB组合", true),
    DIVISIONS_RIVALS("divisions_rivals", "DR模式", true),
    WEEKEND_LEAGUE("weekend_league", "周赛", false);

    private final String code;
    private final String description;
    private final boolean visible;

    GameActionType(String code, String description, boolean visible) {
        this.code = code;
        this.description = description;
        this.visible = visible;
    }

    public String getCode() {
        return code;
    }

    public String getDescription() {
        return description;
    }

    public boolean isVisible() {
        return visible;
    }

    public static GameActionType fromCode(String code) {
        if (code == null || code.isEmpty()) {
            return SQUAD_BATTLE;
        }
        for (GameActionType type : values()) {
            if (type.code.equals(code)) {
                return type;
            }
        }
        return SQUAD_BATTLE;
    }
}
