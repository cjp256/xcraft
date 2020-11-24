import logging
import pathlib
import subprocess
from textwrap import dedent
from time import sleep
from typing import Dict, Optional

from xcraft.executors.lxd_cli import LXDCliExecutor
from xcraft.util import path

from .executed_provider import ExecutedProvider

logger = logging.getLogger(__name__)


class LXDProvider(ExecutedProvider):
    """Base LXD Provider.

    This should be subclassed and extended for each project.

    """

    def __init__(
        self,
        *,
        default_run_environment: Dict[str, str],
        interactive: bool = True,
        executor: Optional[LXDCliExecutor] = None,
        image_name: str = "20.04",
        image_remote_addr: str = "https://cloud-images.ubuntu.com/buildd/releases",
        image_remote_name: str = "snapcraft-buildd-images",
        image_remote_protocol: str = "simplestreams",
        create_ephemeral_instance: bool = False,
        instance_name: str,
        instance_remote: str = "local",
        lxc_path: Optional[pathlib.Path] = None,
        lxd_path: Optional[pathlib.Path] = None,
    ):
        self.default_run_environment = default_run_environment
        self.lxc_path = lxc_path
        self.lxd_path = lxd_path

        self.instance_name = instance_name

        if executor is None:
            executor = LXDCliExecutor(
                default_run_environment=default_run_environment,
                interactive=interactive,
                image_name=image_name,
                image_remote_addr=image_remote_addr,
                image_remote_name=image_remote_name,
                image_remote_protocol=image_remote_protocol,
                create_ephemeral_instance=create_ephemeral_instance,
                instance_name=instance_name,
                instance_remote=instance_remote,
                lxc_path=lxc_path,
            )

        self.executor: LXDCliExecutor = executor
        self._update_executable_paths()

        super().__init__(interactive=interactive, executor=executor)

    def _verify_lxd_version(self) -> None:
        if self.lxd_path is None:
            raise RuntimeError("unset lxd_path")

        proc = subprocess.run(
            [self.lxd_path, "version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        version = float(proc.stdout)
        if version < 4.0:
            raise RuntimeError(
                "LXD version {version!r} is unsupported. Must be >= 4.0."
            )

    def _update_executable_paths(self) -> None:
        if self.lxd_path is None:
            self.lxd_path = path.which("lxd")

        if self.lxc_path is None:
            self.lxc_path = path.which("lxc")

        # Update path for executor.
        self.executor.lxc_path = self.lxc_path

    def _setup_lxd(self) -> None:
        """Ensure LXD is installed with required version."""
        if self.lxd_path is None:
            subprocess.run(["sudo", "snap", "install", "lxd"], check=True)

        if self.lxd_path is None or self.lxc_path is None:
            raise RuntimeError("Failed to install LXD, or lxc/lxd are not in PATH.")

        subprocess.run(
            ["sudo", self.lxd_path.as_posix(), "waitready", "--timeout=30"], check=True
        )
        subprocess.run(["sudo", self.lxd_path.as_posix(), "init", "--auto"], check=True)

        self._verify_lxd_version()

    def _wait_for_systemd(self) -> None:
        # systemctl states we care about here are:
        # - running: The system is fully operational. Process returncode: 0
        # - degraded: The system is operational but one or more units failed.
        #             Process returncode: 1
        for i in range(40):
            proc = self.executor.execute_run(
                ["systemctl", "is-system-running"], stdout=subprocess.PIPE
            )
            if proc.stdout is not None:
                running_state = proc.stdout.decode().strip()
                if running_state in ["running", "degraded"]:
                    break
                logger.debug(f"systemctl is-system-running: {running_state!r}")
                sleep(0.5)

    def _wait_for_network(self) -> None:
        logger.info("Waiting for network to be ready...")
        for i in range(40):
            proc = self.executor.execute_run(
                ["getent", "hosts", "snapcraft.io"], stdout=subprocess.DEVNULL
            )
            if proc.returncode == 0:
                break
            sleep(0.5)
        else:
            logger.warning("Failed to setup networking.")

    def _prepare_instance(self) -> None:
        self._install_file(
            path="/etc/systemd/network/10-eth0.network",
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
            ),
            permissions="0644",
        )

        self._install_file(
            path="/etc/hostname", content=self.instance_name, permissions="0644"
        )

        self._wait_for_systemd()

        # Use resolv.conf managed by systemd-resolved.
        self.executor.execute_run(
            ["ln", "-sf", "/run/systemd/resolve/resolv.conf", "/etc/resolv.conf"],
            check=True,
        )

        self.executor.execute_run(
            ["systemctl", "enable", "systemd-resolved"], check=True
        )
        self.executor.execute_run(
            ["systemctl", "enable", "systemd-networkd"], check=True
        )

        self.executor.execute_run(
            ["systemctl", "restart", "systemd-resolved"], check=True
        )
        self.executor.execute_run(
            ["systemctl", "restart", "systemd-networkd"], check=True
        )

        self._wait_for_network()

        # Setup snapd to bootstrap.
        self.executor.execute_run(["apt-get", "update"], check=True)

        # First install fuse and udev, snapd requires them.
        # Snapcraft requires dirmngr
        self.executor.execute_run(
            ["apt-get", "install", "dirmngr", "udev", "fuse", "--yes"], check=True,
        )

        # the system needs networking
        self.executor.execute_run(["systemctl", "enable", "systemd-udevd"], check=True)
        self.executor.execute_run(["systemctl", "start", "systemd-udevd"], check=True)

        # And only then install snapd.
        self.executor.execute_run(
            ["apt-get", "install", "snapd", "sudo", "--yes"], check=True
        )
        self.executor.execute_run(["systemctl", "start", "snapd"], check=True)
        self.executor.execute_run(["snap", "wait", "system", "seed.loaded"], check=True)

    def setup(self) -> None:
        self._setup_lxd()
        self.executor.__enter__()
        self._prepare_instance()

    def teardown(self, *, clean: bool = False) -> None:
        self.executor.teardown(clean=clean)
