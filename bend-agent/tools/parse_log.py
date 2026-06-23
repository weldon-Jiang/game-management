import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else r"logs/agent.log"
keys = [
    "STEP4", "account_switcher", "账号门禁", "场景", "OCR", "weldon",
    "start_game", "AUTOMATING", "automation_failed", "MAIN_MENU",
    "ensure_target", "切换", "档案", "launch_fc", "entry_survey",
    "Step4", "game_automation", "account_gate", "不匹配", "匹配",
]
date_filter = sys.argv[2] if len(sys.argv) > 2 else "2026-06-23"

with open(path, "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if date_filter not in line:
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = o.get("message", "")
        name = o.get("name", "")
        if any(k in msg or k in name for k in keys):
            print(f"{i}|{o['asctime']}|{name}|{msg[:240]}")
