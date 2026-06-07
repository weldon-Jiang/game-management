-- Add Xbox profile list position for game account switching
ALTER TABLE `game_account`
    ADD COLUMN `position_index` INT DEFAULT NULL COMMENT 'Xbox「您是谁」列表位置，0=最上方' AFTER `priority`;
