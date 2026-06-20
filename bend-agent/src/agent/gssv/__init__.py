"""auth / discovery / xhome_stream 共用的 GSSV HTTP 层。"""

from .client import GssvClient
from .endpoints import GssvEndpoints
from .region_resolver import extract_xhome_regions, select_xhome_base_uri

__all__ = [
    "GssvClient",
    "GssvEndpoints",
    "extract_xhome_regions",
    "select_xhome_base_uri",
]
