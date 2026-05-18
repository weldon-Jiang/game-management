#!/bin/bash
mysql -u root -p'D@GAMECeKfidb' bend_platform <<EOF
ALTER TABLE task ADD COLUMN xbox_host_id VARCHAR(36) DEFAULT NULL COMMENT '使用的Xbox主机ID' AFTER game_account_id;
CREATE INDEX idx_xbox_host_id ON task(xbox_host_id);
SELECT 'Migration completed' AS status;
EOF
