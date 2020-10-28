import logging
from typing import List

logger = logging.getLogger(__name__)


class MycraftHostProviderNoExecutor:
    """Option to bypass executor."""

    def __init__(self) -> None:
        pass

    def execute_step(self, step: str, step_args: List[str]) -> None:
        """Pass-through run command."""
        # call directly into snapcraft's lifecycle, something like:
        # from snapcraft.cli import lifecycle
        # lifecycle._execute(...)
