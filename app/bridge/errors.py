from __future__ import annotations


class BridgeError(Exception):
    """Base class for bridge-owned workflow failures."""


class BridgeConfigurationError(BridgeError):
    """Raised when the bridge cannot operate because its own config is missing."""


class BridgeConflictError(BridgeError):
    """Raised when a caller is not aligned with the current bridge head."""


class BridgeStateError(BridgeError):
    """Raised when bridge-owned state could not be read or updated safely."""
