"""Shared GSSV HTTP layer for auth / discovery / xhome_stream."""

from .client import GssvClient
from .endpoints import GssvEndpoints

__all__ = ["GssvClient", "GssvEndpoints"]
