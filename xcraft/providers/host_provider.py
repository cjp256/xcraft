import logging

from xcraft.providers.executors import HostExecutor

from .provider import Provider

logger = logging.getLogger(__name__)


class HostProvider(Provider):
    """Run commands directly on host."""

    def __init__(
        self, *, sudo: bool = True, sudo_user: str = "root", interactive: bool = True
    ) -> None:
        super().__init__(interactive=interactive)
        self.executor = HostExecutor(
            interactive=interactive,
            sudo=sudo,
            sudo_user=sudo_user,
        )

    def __enter__(self) -> "HostProvider":
        self.executor.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.executor.__exit__()
