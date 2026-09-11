"""Interfaces for future model runners."""

from abc import ABC, abstractmethod

from .models import ModelSpec


class ModelRunner(ABC):
    @abstractmethod
    def run(self, model: ModelSpec, prompt: str) -> str:
        """Run a model; concrete runtimes will implement this later."""
        raise NotImplementedError
