import logging
import os
import pathlib
import subprocess
import tempfile
from textwrap import dedent
from time import sleep
from typing import Any, Dict, List, Optional

from ..executors import Executor
from .lxc import LXC

logger = logging.getLogger(__name__)


class LXDInstance(Executor):
    """LXD Instance Lifecycle."""

    def __init__(
        self,
        *,
        image: str,
        name: str,
        project: str = "default",
        remote: str = "local",
        lxc: Optional[LXC] = None,
    ):
        self.image = image
        self.name = name
        self.project = project
        self.remote = remote
        if lxc is None:
            self.lxc = LXC()
        else:
            self.lxc = lxc

    def create_file(
        self,
        *,
        destination: pathlib.Path,
        content: bytes,
        file_mode: str,
        gid: int = 0,
        uid: int = 0,
    ) -> None:
        """Create file with content and file mode."""
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(content)
            tf.flush()

        self.lxc.file_push(
            instance=self.name,
            source=pathlib.Path(tf.name),
            destination=destination,
            mode=file_mode,
            gid=str(gid),
            uid=str(uid),
            project=self.project,
            remote=self.remote,
        )

        os.unlink(tf.name)

    def delete(self, force: bool = True) -> None:
        return self.lxc.delete(
            instance=self.name,
            project=self.project,
            remote=self.remote,
            force=force,
        )

    def execute_popen(self, command: List[str], **kwargs) -> subprocess.Popen:
        return self.lxc.exec(
            instance=self.name,
            command=command,
            project=self.project,
            remote=self.remote,
            runner=subprocess.Popen,
            **kwargs,
        )

    def execute_run(self, command: List[str], **kwargs) -> subprocess.CompletedProcess:
        return self.lxc.exec(
            instance=self.name,
            command=command,
            project=self.project,
            remote=self.remote,
            runner=subprocess.run,
            **kwargs,
        )

    def exists(self) -> bool:
        return self.get_state() is not None

    def get_state(self) -> Optional[Dict[str, Any]]:
        instances = self.lxc.list(
            instance=self.name, project=self.project, remote=self.remote
        )

        # lxc returns a filter instances starting with instance name rather
        # than the exact instance.  Find the exact match...
        for instance in instances:
            if instance["name"] == self.name:
                return instance

        return None

    def is_mounted(self, *, source: pathlib.Path, destination: pathlib.Path) -> bool:
        devices = self.lxc.config_device_show(
            instance=self.name, project=self.project, remote=self.remote
        )
        disks = [d for d in devices.values() if d.get("type") == "disk"]

        return any(
            disk.get("path") == destination.as_posix()
            and disk.get("source") == source.as_posix()
            for disk in disks
        )

    def is_running(self) -> bool:
        """Check if instance is running."""
        state = self.get_state()
        if state is None:
            return False

        return state.get("status") == "Running"

    def launch(
        self,
        *,
        image: str,
        image_remote: str,
        uid: str = str(os.getuid()),
        ephemeral: bool = True,
    ) -> None:
        config_keys = dict()
        config_keys["raw.idmap"] = f"both {uid!s} 0"

        if self._host_supports_mknod():
            config_keys["security.syscalls.intercept.mknod"] = "true"

        self.lxc.launch(
            config_keys=config_keys,
            ephemeral=ephemeral,
            instance=self.name,
            image=image,
            image_remote=image_remote,
            project=self.project,
            remote=self.remote,
        )

    def mount(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        """Mount host source directory to target mount point.

        Checks first to see if already mounted."""
        if self.is_mounted(source=source, destination=destination):
            return

        self.lxc.config_device_add_disk(
            instance=self.name,
            source=source,
            destination=destination,
            project=self.project,
            remote=self.remote,
        )

    def setup(self) -> None:
        self.create_file(
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

        self.create_file(
            destination=pathlib.Path("/etc/hostname"),
            content=self.name.encode(),
            file_mode="0644",
        )

        self._setup_wait_for_systemd()

        self.execute_run(
            command=["systemctl", "enable", "systemd-networkd"], check=True
        )

        self.execute_run(
            command=["systemctl", "restart", "systemd-networkd"], check=True
        )

        # Use resolv.conf managed by systemd-resolved.
        self.execute_run(
            command=[
                "ln",
                "-sf",
                "/run/systemd/resolve/resolv.conf",
                "/etc/resolv.conf",
            ],
            check=True,
        )

        self.execute_run(
            command=["systemctl", "enable", "systemd-resolved"], check=True
        )

        self.execute_run(
            command=["systemctl", "restart", "systemd-resolved"], check=True
        )

        self.execute_run(
            command=["systemctl", "restart", "systemd-networkd"], check=True
        )

        self._setup_wait_for_network()

        # Setup snapd to bootstrap.
        self.execute_run(command=["apt-get", "update"], check=True)

        # First install fuse and udev, snapd requires them.
        # Snapcraft requires dirmngr
        self.execute_run(
            command=[
                "apt-get",
                "install",
                "dirmngr",
                "lsb-release",
                "udev",
                "fuse",
                "--yes",
            ],
            check=True,
        )

        # the system needs networking
        self.execute_run(command=["systemctl", "enable", "systemd-udevd"], check=True)
        self.execute_run(command=["systemctl", "start", "systemd-udevd"], check=True)

        # And only then install snapd.
        self.execute_run(
            command=["apt-get", "install", "snapd", "sudo", "--yes"], check=True
        )
        self.execute_run(command=["systemctl", "start", "snapd"], check=True)

        proc = self.execute_run(
            command=["lsb_release", "-rs"], check=True, stdout=subprocess.PIPE
        )
        release = proc.stdout.decode()

        if float(release) >= 18.04:
            self.execute_run(
                command=["snap", "wait", "system", "seed.loaded"], check=True
            )
        else:
            # XXX: better way to ensure snapd is ready on core?
            sleep(5)

    def _host_supports_mknod(self) -> bool:
        """Enable mknod in container, if possible.

        See: https://linuxcontainers.org/lxd/docs/master/syscall-interception
        """
        cfg = self.lxc.info(project=self.project, remote=self.remote)
        env = cfg.get("environment", dict())
        kernel_features = env.get("kernel_features", dict())
        seccomp_listener = kernel_features.get("seccomp_listener", "false")

        return seccomp_listener == "true"

    def _setup_wait_for_network(self) -> None:
        logger.info("Waiting for network to be ready...")
        for i in range(40):
            proc = self.execute_run(
                command=["getent", "hosts", "snapcraft.io"], stdout=subprocess.DEVNULL
            )
            if proc.returncode == 0:
                break
            sleep(0.5)
        else:
            logger.warning("Failed to setup networking.")

    def _setup_wait_for_systemd(self) -> None:
        # systemctl states we care about here are:
        # - running: The system is fully operational. Process returncode: 0
        # - degraded: The system is operational but one or more units failed.
        #             Process returncode: 1
        for i in range(40):
            proc = self.execute_run(
                command=["systemctl", "is-system-running"], stdout=subprocess.PIPE
            )
            if proc.stdout is not None:
                running_state = proc.stdout.decode().strip()
                if running_state in ["running", "degraded"]:
                    break
                logger.debug(f"systemctl is-system-running: {running_state!r}")
                sleep(0.5)

    def start(self) -> None:
        self.lxc.start(instance=self.name, project=self.project, remote=self.remote)

    def stop(self) -> None:
        self.lxc.stop(instance=self.name, project=self.project, remote=self.remote)

    def supports_mount(self) -> bool:
        return self.remote == "local"

    def sync_from(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        logger.info(f"Syncing env:{source} -> host:{destination}...")
        # TODO: check if mount makes source == destination, skip if so.
        if self.is_target_file(source):
            self.lxc.file_pull(
                instance=self.name,
                source=source,
                destination=destination,
                project=self.project,
                remote=self.remote,
                create_dirs=True,
            )
        elif self.is_target_directory(target=source):
            self.lxc.file_pull(
                instance=self.name,
                source=source,
                destination=destination,
                project=self.project,
                remote=self.remote,
                create_dirs=True,
                recursive=True,
            )
            # TODO: use mount() if available
            self.naive_directory_sync_from(source=source, destination=destination)
        else:
            raise FileNotFoundError(f"Source {source} not found.")

    def sync_to(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        # TODO: check if mounted, skip sync if source == destination
        logger.info(f"Syncing host:{source} -> env:{destination}...")
        if source.is_file():
            self.lxc.file_push(
                instance=self.name,
                source=source,
                destination=destination,
                project=self.project,
                remote=self.remote,
            )
        elif source.is_dir():
            # TODO: use mount() if available
            self.naive_directory_sync_to(
                source=source, destination=destination, delete=True
            )
        else:
            raise FileNotFoundError(f"Source {source} not found.")
