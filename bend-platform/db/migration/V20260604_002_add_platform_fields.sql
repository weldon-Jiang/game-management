-- Add platform type fields for multi-console support (xbox / playstation)

ALTER TABLE streaming_account
    ADD COLUMN platform VARCHAR(32) NOT NULL DEFAULT 'xbox' COMMENT '平台类型: xbox, playstation' AFTER auth_code;

ALTER TABLE game_account
    ADD COLUMN platform VARCHAR(32) NOT NULL DEFAULT 'xbox' COMMENT '平台类型: xbox, playstation' AFTER merchant_id;

ALTER TABLE xbox_host
    ADD COLUMN platform VARCHAR(32) NOT NULL DEFAULT 'xbox' COMMENT '平台类型: xbox, playstation' AFTER merchant_id;
