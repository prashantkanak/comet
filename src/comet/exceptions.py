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


class LLMError(CometError):
    """Raised when an LLM call or its structured output fails."""

    error_code = "LLM_ERROR"
    transient = False

    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        transient: bool = False,
    ) -> None:
        super().__init__(message)
        if error_code is not None:
            self.error_code = error_code
        self.transient = transient


class StructuredOutputValidationError(LLMError):
    error_code = "STRUCTURED_OUTPUT_VALIDATION_ERROR"


class LLMProviderError(LLMError):
    error_code = "LLM_PROVIDER_ERROR"


class EmailGenerationError(LLMError):
    error_code = "EMAIL_GENERATION_ERROR"


class SummaryGenerationError(LLMError):
    error_code = "SUMMARY_GENERATION_ERROR"
