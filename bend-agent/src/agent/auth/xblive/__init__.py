"""xblive SISU 认证（对齐 D:\\auto-xbox\\xblive\\xblauth.py）。"""

from .authenticator import XbliveAuthenticator, authenticate_account
from .errors import ERRXS_OK, error_code_name
from .models import XbliveAuthResult, XbliveCompatXboxTokens

__all__ = [
    "XbliveAuthenticator",
    "authenticate_account",
    "XbliveAuthResult",
    "XbliveCompatXboxTokens",
    "ERRXS_OK",
    "error_code_name",
]
