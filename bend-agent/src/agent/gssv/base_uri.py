"""Resolve GSSV base URI from task context or credentials."""

from typing import Any, Optional

DEFAULT_GSSV_BASE_URI = "https://uks.core.gssv-play-prodxhome.xboxlive.com"


def normalize_gssv_base_uri(uri: Optional[str]) -> str:
    if not uri or not str(uri).strip():
        return DEFAULT_GSSV_BASE_URI
    return str(uri).strip().rstrip("/")


def resolve_gssv_base_uri(source: Any) -> str:
    """Extract GSSV base URI from AgentTaskContext, StreamingCredentials, or XboxTokens."""
    if source is None:
        return DEFAULT_GSSV_BASE_URI

    direct = getattr(source, "gssv_base_uri", None)
    if direct:
        return normalize_gssv_base_uri(direct)

    xbox_tokens = getattr(source, "xbox_tokens", None)
    if xbox_tokens:
        uri = getattr(xbox_tokens, "gssv_base_uri", None) or getattr(
            xbox_tokens, "base_uri", None
        )
        if uri:
            return normalize_gssv_base_uri(uri)

    return DEFAULT_GSSV_BASE_URI
