import enum
import logging
import pathlib
import subprocess
from textwrap import dedent
from time import sleep

from ..executors import Executor
from .image import Image

logger = logging.getLogger(__name__)


class BuilddImageAlias(enum.Enum):
    XENIAL = 16.04
    BIONIC = 18.04
    FOCAL = 20.04


class BuilddImage(Image):
    """Buildd Image Configurator.

    Sets up networking, installs snapd and its dependencies."""

    def __init__(
        self,
        *,
        alias: BuilddImageAlias,
        hostname: str = "craft-builder",
    ):
        super().__init__(
            version=str(alias.value),
            revision=0,
        )

        self.alias = alias
        self.hostname = hostname

    def setup(self, *, executor: Executor) -> None:
        executor.create_file(
            destination=pathlib.Path("/etc/systemd/network/10-eth0.network"),
            content=dedent(
                """
                [Match]
                Name=eth0

                [Network]
                DHCP=ipv4
                LinkLocalAddressing=ipv6

                [DHCP]
                RouteMetric=100
                UseMTU=true
                """
            ).encode(),
            file_mode="0644",
        )

        executor.create_file(
            destination=pathlib.Path("/etc/hostname"),
            content=self.hostname.encode(),
            file_mode="0644",
        )

        self._setup_wait_for_systemd(executor=executor)

        executor.execute_run(
            command=["systemctl", "enable", "systemd-networkd"], check=True
        )

        executor.execute_run(
            command=["systemctl", "restart", "systemd-networkd"], check=True
        )

        # Use resolv.conf managed by systemd-resolved.
        executor.execute_run(
            command=[
                "ln",
                "-sf",
                "/run/systemd/resolve/resolv.conf",
                "/etc/resolv.conf",
            ],
            check=True,
        )

        executor.execute_run(
            command=["systemctl", "enable", "systemd-resolved"], check=True
        )

        executor.execute_run(
            command=["systemctl", "restart", "systemd-resolved"], check=True
        )

        executor.execute_run(
            command=["systemctl", "restart", "systemd-networkd"], check=True
        )

        self._setup_wait_for_network(executor=executor)

        executor.execute_run(command=["apt-get", "update"], check=True)

        # Install commonly required packages:
        # - dirmngr: for configuring apt GPG keyrings
        # - fuse: for snapd
        # - udev: for snapd
        executor.execute_run(
            command=[
                "apt-get",
                "install",
                "dirmngr",
                "fuse",
                "udev",
                "--yes",
            ],
            check=True,
        )

        executor.execute_run(
            command=["systemctl", "enable", "systemd-udevd"], check=True
        )
        executor.execute_run(
            command=["systemctl", "start", "systemd-udevd"], check=True
        )

        # Snapd depends on systemd-udev and above dependencies (fuse, udev).
        executor.execute_run(
            command=["apt-get", "install", "snapd", "sudo", "--yes"], check=True
        )
        executor.execute_run(command=["systemctl", "start", "snapd"], check=True)

        if self.alias.value >= 18.04:
            executor.execute_run(
                command=["snap", "wait", "system", "seed.loaded"], check=True
            )
        else:
            # XXX: better way to ensure snapd is ready on core?
            sleep(5)

    def _setup_wait_for_network(self, *, executor: Executor) -> None:
        logger.info("Waiting for network to be ready...")
        for i in range(40):
            proc = executor.execute_run(
                command=["getent", "hosts", "snapcraft.io"], stdout=subprocess.DEVNULL
            )
            if proc.returncode == 0:
                break

            sleep(0.5)
        else:
            logger.warning("Failed to setup networking.")

    def _setup_wait_for_systemd(self, *, executor: Executor) -> None:
        # systemctl states we care about here are:
        # - running: The system is fully operational. Process returncode: 0
        # - degraded: The system is operational but one or more units failed.
        #             Process returncode: 1
        for i in range(40):
            proc = executor.execute_run(
                command=["systemctl", "is-system-running"], stdout=subprocess.PIPE
            )

            running_state = proc.stdout.decode().strip()
            if running_state in ["running", "degraded"]:
                break

            logger.debug(f"systemctl is-system-running: {running_state!r}")
            sleep(0.5)
        else:
            logger.warning(f"Systemd not rFailed to ait for systemd: {proc.stdout}.")
