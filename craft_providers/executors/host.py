import logging
import pathlib
import shlex
import shutil
import subprocess
from typing import Any, Dict, List

from .executor import Executor

logger = logging.getLogger(__name__)


class HostExecutor(Executor):
    """Run commands directly on host."""

    def __init__(self, *, sudo: bool = True, sudo_user: str = "root") -> None:
        self.sudo = sudo
        self.sudo_user = sudo_user

    def _prepare_execute_args(
        self, command: List[str], kwargs: Dict[str, Any]
    ) -> List[str]:
        """Formulate command, accounting for possible env & cwd."""
        env = kwargs.pop("env", dict())

        final_cmd = ["env", "-"]
        final_cmd += [f"{k}={v}" for k, v in env.items()]

        if self.sudo:
            final_cmd += ["sudo", "-H", "-u", self.sudo_user]

        final_cmd += command

        quoted = " ".join([shlex.quote(c) for c in final_cmd])
        logger.info(f"Executing: {quoted}")

        return final_cmd

    def clean(self) -> None:
        pass

    def execute_run(self, command: List[str], **kwargs) -> subprocess.CompletedProcess:
        command = self._prepare_execute_args(command=command, kwargs=kwargs)
        return subprocess.run(command, **kwargs)

    def execute_popen(self, command: List[str], **kwargs) -> subprocess.Popen:
        command = self._prepare_execute_args(command=command, kwargs=kwargs)
        return subprocess.Popen(command, **kwargs)

    def mount(self, *, source: pathlib.Path, destination: pathlib.Path) -> bool:
        return False

    def sync_to(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        if source.is_file():
            shutil.copy2(source, destination)
        elif source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            raise FileNotFoundError(f"Source {source} not found.")

    def sync_from(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        if source.is_file():
            shutil.copy2(source, destination)
        elif source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            raise FileNotFoundError(f"Source {source} not found.")

    def setup(self) -> None:
        pass

    def teardown(self, *, clean: bool = False) -> None:
        pass
