import logging
import os
import shutil
import sys
from typing import Dict, List

from xcraft.providers import HostProvider

logger = logging.getLogger(__name__)


class MycraftHostProviderUsingExecutor(HostProvider):
    """Run commands directly on host using local executor.

    This provider assumes that Mycraft has a "snapcraft-builder"
    or similar entry point to call into with the executor.

    """

    def __init__(self) -> None:
        super().__init__(sudo=False, sudo_user=None)
        self.snapcraft_builder = shutil.which("snapcraft")

    def __enter__(self) -> "MycraftHostProvider":
        if sys.platform != "linux":
            raise RuntimeError("Host provider not support on this platform.")
        super().__enter__()

    def run_env(self) -> Dict[str, str]:
        """Host mode will copy host environment flags."""
        run_env = os.environ.copy()
        run_env["SNAPCRAFT_BUILD_ENVIRONMENT"] = "host"
        return run_env

    def run_cwd(self) -> str:
        """Host mode runs in current directory."""
        return os.getcwd()

    def execute_step(self, step: str, step_args: List[str]) -> None:
        """Pass-through run command."""
        command = [self.snapcraft_builder, step, *step_args]
        self.executor.execute_run(command, env=self.run_env(), cwd=self.run_cwd())
