"""PKCE code_verifier / code_challenge 生成。"""

import base64
import hashlib
import secrets


def generate_pkce_pair() -> tuple:
    code_verifier = (
        base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
    )
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge
