"""auth / discovery / xhome_stream 共用的 GSSV HTTP 层。"""

from .client import GssvClient
from .endpoints import GssvEndpoints
from .region_resolver import extract_xhome_regions, select_xhome_base_uri
from .stream_mode import get_stream_mode, is_cloud_stream_mode

__all__ = [
    "GssvClient",
    "GssvEndpoints",
    "extract_xhome_regions",
    "select_xhome_base_uri",
    "get_stream_mode",
    "is_cloud_stream_mode",
]
