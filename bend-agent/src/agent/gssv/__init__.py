"""auth / discovery / xhome_stream 共用的 GSSV HTTP 层。"""

from .client import GssvClient
from .endpoints import GssvEndpoints

__all__ = ["GssvClient", "GssvEndpoints"]
