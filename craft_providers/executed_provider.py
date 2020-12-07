import logging
from abc import abstractmethod

from .executors.executor import Executor
from .provider import Provider

logger = logging.getLogger(__name__)


class ExecutedProvider(Provider):
    """Guarantees availability of executor and provides common helper methods."""

    @abstractmethod
    def setup(self) -> Executor:
        """Launch environment, returning build instance executor."""

        ...
