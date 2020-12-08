import logging
from abc import ABC, abstractmethod

from ..executors import Executor

logger = logging.getLogger(__name__)


class Image(ABC):
    """Image Configurator."""

    def __init__(
        self,
        *,
        version: str,
        revision: int,
    ):
        self.version = version
        self.revision = revision

    @abstractmethod
    def setup(self, *, executor: Executor) -> None:
        ...
