"""TUI-owned JSON-RPC client and DTO adaptation layer."""

from .client import EngineClient, EngineRpcError

__all__ = ["EngineClient", "EngineRpcError"]
