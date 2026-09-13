"""Application-specific exceptions."""


class CometError(Exception):
    """Base exception for Comet AI errors."""


class ConfigurationError(CometError):
    """Raised when application configuration is invalid or incomplete."""


class IngestionError(CometError):
    """Raised when a document cannot be discovered or loaded."""

    error_code = "INGESTION_ERROR"

    def __init__(self, message: str, *, error_code: str | None = None) -> None:
        super().__init__(message)
        if error_code is not None:
            self.error_code = error_code


class UnsupportedDocumentError(IngestionError):
    error_code = "UNSUPPORTED_FILE_TYPE"


class DocumentReadError(IngestionError):
    error_code = "DOCUMENT_READ_ERROR"


class EmptyDocumentError(IngestionError):
    error_code = "EMPTY_DOCUMENT"
