import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class Provider(ABC):
    """Provide an execution environment for a project.

    Provides the ability to create/launch the environment, execute commands, and
    move data in/out of the environment.

    """

    def __init__(
        self,
        *,
        interactive: bool = True,
    ) -> None:
        """Initialize provider.

        :param interactive: Ask the user before making any privileged actions on
          the host, such as installing an application.  Allows user to be asked
          (via input()) for configuration, if required.

        """
        self.interactive = interactive

    @abstractmethod
    def __enter__(self) -> "Provider":
        """Launch environment, performing any required setup.

        If interactive was set to True, prompt the user for privileged
        configuration changes using input(), e.g. installing dependencies.

        The executor will launch the instance (if applicable), the Provider
        extens that to include any additional setup that may be required, e.g.
        updating apt, installing required packages. Upon completion of this, it
        is expected that the environment is ready for the user-provided build
        step(s).

        """
        ...

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Non-destructive tear-down of environment.

        Unmount, close, and shutdown any resources.

        """
        ...

    @abstractmethod
    def clean(self) -> None:
        """Destructive cleanup of environmnet.

        Purges any artifacts related to the creation of the environment.
        """
        ...

    @abstractmethod
    def execute(self) -> None:
        """Do your thing."""

        ...
