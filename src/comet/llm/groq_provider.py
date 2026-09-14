"""Groq adapter: OpenAI-compatible chat completions."""

from comet.llm.openai_provider import OpenAILLMProvider

DEFAULT_GROQ_MODEL = "qwen/qwen3.8-27b"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqLLMProvider(OpenAILLMProvider):
    """Call Groq and validate structured extraction as ComplaintCase."""

    def __init__(
        self,
        api_key: str,
        model_name: str | None = None,
        *,
        client: object | None = None,
    ) -> None:
        super().__init__(
            api_key,
            model_name or DEFAULT_GROQ_MODEL,
            client=client,
            base_url=GROQ_BASE_URL,
            # Qwen3.8 thinks by default; that breaks JSON extraction.
            request_extras={"reasoning_effort": "none"},
            # Groq free-tier often allows one in-flight request; email||summary
            # concurrency otherwise 429s the summary call.
            serialize_requests=True,
        )
