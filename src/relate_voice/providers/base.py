from __future__ import annotations

from enum import StrEnum
from typing import Protocol


class ProviderErrorCategory(StrEnum):
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    TRANSIENT = "transient"
    UNAVAILABLE = "unavailable"
    AUTHENTICATION = "authentication"
    INVALID_REQUEST = "invalid_request"
    CONFIGURATION = "configuration"
    APPLICATION = "application"


FALLBACK_ELIGIBLE_CATEGORIES = frozenset(
    {
        ProviderErrorCategory.RATE_LIMIT,
        ProviderErrorCategory.TIMEOUT,
        ProviderErrorCategory.TRANSIENT,
        ProviderErrorCategory.UNAVAILABLE,
    }
)


class ProviderError(RuntimeError):
    def __init__(self, category: ProviderErrorCategory, message: str) -> None:
        super().__init__(message)
        self.category = category

    @property
    def fallback_eligible(self) -> bool:
        return self.category in FALLBACK_ELIGIBLE_CATEGORIES


class ProviderFactory(Protocol):
    def __call__(self, spec: object, environment: dict[str, str]) -> object: ...
