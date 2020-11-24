import logging
import pathlib
import subprocess
from abc import ABC, abstractmethod
from typing import List

logger = logging.getLogger(__name__)


class Executor(ABC):
    """Provide an execution environment for a project.

    Provides the ability to create/launch the environment, execute commands, and
    move data in/out of the environment.

    """

    def __init__(self, *, interactive: bool = True,) -> None:
        """Initialize provider.

        :param interactive: Ask the user before making any privileged actions on
          the host, such as installing an application.  Allows user to be asked
          (via input()) for configuration, if required.

        """
        self.interactive = interactive

    @abstractmethod
    def create_file(
        self, *, destination: pathlib.Path, content: bytes, file_mode: str
    ) -> None:
        """Create file with content and file mode."""
        ...

    def __enter__(self) -> "Executor":
        """Launch environment, performing any required setup.

        If interactive was set to True, prompt the user for privileged
        configuration changes using input(), e.g. installing dependencies.

        """

        self.setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Non-destructive tear-down of environment.

        Unmount, close, and shutdown any resources.

        """

        self.teardown()

    @abstractmethod
    def execute_run(self, command: List[str], **kwargs) -> subprocess.CompletedProcess:
        """Execute command in instance, using subprocess.run().

        If `env` is in kwargs, it will be applied to the target runtime
        environment, not the host's.

        """
        ...

    @abstractmethod
    def execute_popen(self, command: List[str], **kwargs) -> subprocess.Popen:
        """Execute command in instance, using subprocess.Popen().

        If `env` is in kwargs, it will be applied to the target runtime
        environment, not the host's.

        """
        ...

    @abstractmethod
    def exists(self) -> bool:
        """Check if executed environment exists and/or ready."""

        ...

    @abstractmethod
    def sync_from(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        """Copy source file/directory from environment to host destination.

        Standard "cp -r" rules apply:
        - if source is directory, copy happens recursively.
        - if destination exists, source will be copied into destination.

        Providing this as an abstract method allows the provider to implement
        the most performant option available.

        """
        ...

    @abstractmethod
    def sync_to(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        """Copy host source file/directory into environment at destination.

        Standard "cp -r" rules apply:
        - if source is directory, copy happens recursively.
        - if destination exists, source will be copied into destination.

        Providing this as an abstract method allows the provider to implement
        the most performant option available.

        """
        ...

    @abstractmethod
    def setup(self) -> None:
        """Launch environment."""

        ...

    @abstractmethod
    def supports_mount(self) -> bool:
        """Flag if executor can mount to target."""

        ...

    @abstractmethod
    def teardown(self, *, clean: bool = False) -> None:
        """Tear down environment."""

        ...
