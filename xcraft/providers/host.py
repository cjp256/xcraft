import logging

from xcraft.executors.executor import Executor
from xcraft.executors.host import HostExecutor

from .executed_provider import ExecutedProvider

logger = logging.getLogger(__name__)


class HostProvider(ExecutedProvider):
    """Run commands directly on host."""

    def __init__(
        self,
        *,
        executor: Executor,
        sudo: bool = True,
        sudo_user: str = "root",
        interactive: bool = True
    ) -> None:

        if executor is None:
            executor = HostExecutor(
                interactive=interactive,
                sudo=sudo,
                sudo_user=sudo_user,
            )
        super().__init__(interactive=interactive, executor=executor)

    def setup(self) -> None:
        pass

    def teardown(self) -> None:
        pass
