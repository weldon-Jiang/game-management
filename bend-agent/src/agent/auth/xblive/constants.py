"""xblive 认证常量（对齐 xblauth.py Defines）。"""

# Token 有效期缓存阈值（秒）
XHOME_TOKEN_LIFE_SEC = 4 * 3600 - 60
XSTS_TOKEN_LIFE_SEC = 16 * 3600 - 60
USER_TOKEN_LIFE_SEC = 24 * 3600 - 60

OAUTH_GRANT_AUTHORIZE = "authorization_code"
OAUTH_GRANT_REFRESH = "refresh_token"

APP_ID = "000000004c20a908"
TITLE_ID = "328178078"
REDIRECT_URI = f"ms-xal-{APP_ID}://auth"
SCOPE = "service::user.auth.xboxlive.com::MBI_SSL"

# token_storage JSON 字段名
KEY_DEVICE_TOKEN = "device_token"
KEY_DEVICE_TIME = "device_time"
KEY_USER_TOKEN = "user_token"
KEY_USER_TIME = "user_time"
KEY_SISU_TOKEN = "sisu_token"
KEY_SISU_TIME = "sisu_time"
KEY_XSTS_TOKEN = "xsts_token"
KEY_XSTS_TIME = "xsts_time"
KEY_XHOME_TOKEN = "xhome_token"
KEY_XHOME_TIME = "xhome_time"
KEY_SERVER_ID = "server_id"
KEY_PLAY_PATH = "play_path"
KEY_GAMER_TAG = "gamer_tag"
KEY_GSSV_BASE_URI = "gssv_base_uri"
KEY_USER_ACCESS = "access_token"
KEY_USER_REFRESH = "refresh_token"
