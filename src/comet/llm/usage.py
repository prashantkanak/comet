"""Token usage from chat-completion responses (OpenAI/Groq)."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class TokenUsage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, prompt: int, completion: int, total: int) -> None:
        with self._lock:
            self.calls += 1
            self.prompt_tokens += prompt
            self.completion_tokens += completion
            self.total_tokens += total or (prompt + completion)

    def as_dict(self) -> dict[str, int]:
        with self._lock:
            return {
                "calls": self.calls,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens,
            }


def usage_from_response(response: object) -> tuple[int, int, int] | None:
    raw = getattr(response, "usage", None)
    if raw is None:
        return None
    prompt = _usage_int(raw, "prompt_tokens")
    completion = _usage_int(raw, "completion_tokens")
    total = _usage_int(raw, "total_tokens")
    if prompt == completion == total == 0:
        return None
    return prompt, completion, total or (prompt + completion)


def _usage_int(raw: object, name: str) -> int:
    if isinstance(raw, dict):
        value = raw.get(name, 0)
    else:
        value = getattr(raw, name, 0)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def usage_dict(provider: object) -> dict[str, int] | None:
    usage = getattr(provider, "token_usage", None)
    if not isinstance(usage, TokenUsage) or usage.calls == 0:
        return None
    return usage.as_dict()
