import logging
from typing import Dict

from ..executed_provider import ExecutedProvider
from ..executors.executor import Executor
from ..executors.host import HostExecutor

logger = logging.getLogger(__name__)


class HostProvider(ExecutedProvider):
    """Run commands directly on host."""

    def __init__(
        self,
        *,
        default_run_environment: Dict[str, str],
        executor: Executor,
        sudo: bool = True,
        sudo_user: str = "root",
    ) -> None:

        if executor is None:
            executor = HostExecutor(
                sudo=sudo,
                sudo_user=sudo_user,
            )

        super().__init__(
            executor=executor,
            default_run_environment=default_run_environment,
        )

    def setup(self):
        # TODO Instance class
        pass

    def teardown(self, *, clean: bool = False) -> None:
        pass
