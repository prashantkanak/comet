"""Application-specific exceptions."""


class CometError(Exception):
    """Base exception for Comet AI errors."""


class ConfigurationError(CometError):
    """Raised when application configuration is invalid or incomplete."""
