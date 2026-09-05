from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class MockProvider:
    kind: str
    model: str


class HasModel(Protocol):
    model: str


def build_mock(kind: str) -> Callable[[HasModel, Mapping[str, str]], MockProvider]:
    return lambda spec, environment: MockProvider(kind=kind, model=spec.model)
