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
        self.lxc_path = lxc_path
        self.lxd_path = lxd_path

        self.image_name = image_name
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

        super().__init__(
            interactive=interactive,
            executor=executor,
            default_run_environment=default_run_environment,
        )

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

        if float(self.image_name) >= 18.04:
            self.executor.execute_run(
                ["snap", "wait", "system", "seed.loaded"], check=True
            )
        else:
            # XXX: better way to ensure snapd is ready on core?
            sleep(5)

    def setup(self) -> None:
        self._setup_lxd()
        self.lxc.executor.__enter__()
        self._prepare_instance()

    def teardown(self, *, clean: bool = False) -> None:
        if self.lxc._get_instance_state() is None:
            return

        self.lxc.stop()

        if clean:
            self.lxc.delete()

    def create_file(
        self, *, destination: pathlib.Path, content: bytes, file_mode: str
    ) -> None:
        """Create file with content and file mode."""
        temp_file = tempfile.NamedTemporaryFile()
        temp_file.write(content)

        self._run(
            [
                "file",
                "push",
                temp_file.name,
                self.instance_id + destination.as_posix(),
                "--create-dirs",
                "--mode",
                file_mode,
                "--gid",
                "0",
                "--uid",
                "0",
            ],
            check=True,
        )

    def _get_config_key_idmap(self, *, uid: str = str(os.getuid())) -> str:
        """Map specified uid on host to root in container."""
        return f"raw.idmap=both {uid!s} 0"

    def _get_config_key_mknod(self) -> str:
        """Enable mknod in container, if possible.

        See: https://linuxcontainers.org/lxd/docs/master/syscall-interception
        """
        cfg = self._get_server_config()
        env = cfg.get("environment", dict())
        kernel_features = env.get("kernel_features", dict())
        seccomp_listener = kernel_features.get("seccomp_listener", "false")

        if seccomp_listener == "true":
            return "security.syscalls.intercept.mknod=true"

        return "security.syscalls.intercept.mknod=false"

    def _delete(self) -> None:
        self._run(["delete", self.instance_id, "--force"], check=True)

    def _get_devices(self) -> Dict[str, Any]:
        proc = self._run(
            ["config", "device", "show", self.instance_id],
            stdout=subprocess.PIPE,
            check=True,
        )

        return yaml.load(proc.stdout, Loader=yaml.FullLoader)

    def _get_instances(self) -> List[Dict[str, Any]]:
        """Get instance state information."""
        proc = self._run(
            ["list", "--format=yaml", self.instance_id],
            stdout=subprocess.PIPE,
            check=True,
        )

        return yaml.load(proc.stdout, Loader=yaml.FullLoader)

    def _get_instance_state(self) -> Optional[Dict[str, Any]]:
        """Get instance state, if instance exists."""
        instances = self._get_instances()
        if not instances:
            return None

        for instance in self._get_instances():
            if instance["name"] == self.instance_name:
                return instance
        return None

    def _get_remotes(self) -> Dict[str, Any]:
        """Get list of remotes.

        :returns: dictionary with remote name mapping to config.
        """
        proc = self._run(
            ["remote", "list", "--format=yaml"], stdout=subprocess.PIPE, check=True,
        )
        return yaml.load(proc.stdout, Loader=yaml.FullLoader)

    def _get_server_config(self) -> Dict[str, Any]:
        """Get server config that instance is running on."""
        proc = self._run(
            ["info", self.instance_remote + ":"], stdout=subprocess.PIPE, check=True,
        )
        return yaml.load(proc.stdout, Loader=yaml.FullLoader)

    def _is_instance_running(self) -> bool:
        """Check if instance is running."""
        instance_state = self._get_instance_state()
        if instance_state is None:
            return False

        return instance_state["status"] == "Running"

    def _launch(self, *, uid: str = str(os.getuid())) -> None:
        image = ":".join([self.image_remote_name, self.image_name])

        self._run(
            [
                "launch",
                image,
                self.instance_id,
                "--config",
                self._get_config_key_idmap(uid=uid),
                "--config",
                self._get_config_key_mknod(),
            ],
            check=True,
        )

    def _set_config_key(self, key: str, value: str) -> None:
        """Set instance configuration key."""
        self._run(["config", "set", self.instance_id, key, value], check=True)

    def _prepare_execute_args(
        self, command: List[str], kwargs: Dict[str, Any]
    ) -> List[str]:
        """Formulate command, accounting for possible env & cwd."""
        env = kwargs.pop("env", self.default_run_environment)
        cwd = kwargs.pop("cwd", None)

        final_cmd = [str(self.lxc_path), "exec", self.instance_id, "--", "env"]

        if cwd:
            final_cmd += [f"--chdir={cwd}"]

        final_cmd += ["-"]
        final_cmd += [f"{k}={v}" for k, v in env.items()]
        final_cmd += command

        quoted = " ".join([shlex.quote(c) for c in final_cmd])
        logger.info(f"Executing in container: {quoted}")

        return final_cmd

    def _pull_file(self, *, source: str, destination: str) -> None:
        """Get file from instance."""
        self._run(
            ["file", "pull", self.instance_id + source, destination], check=True,
        )

    def _push_file(self, *, source: str, destination: str) -> None:
        """Push file to instance."""
        self._run(
            ["file", "push", source, self.instance_id + destination], check=True,
        )

    def _run(
        self, command: List[str], **subprocess_run_kwargs
    ) -> subprocess.CompletedProcess:
        """Execute command in instance, allowing output to console."""
        command = [str(self.lxc_path), *command]
        quoted = " ".join([shlex.quote(c) for c in command])
        logger.info(f"Executing on host: {quoted}")
        return subprocess.run(command, **subprocess_run_kwargs)

    def _setup_image_remote(self) -> None:
        """Add a public remote."""
        matching_remote = self._get_remotes().get(self.image_remote_name)

        # If remote already configured, nothing to do.
        if matching_remote:
            if (
                matching_remote.get("addr") != self.image_remote_addr
                or matching_remote.get("protocol") != self.image_remote_protocol
            ):
                raise RuntimeError(f"Unexpected LXD remote: {matching_remote!r}")
            return

        # Remote not found, add it.
        self._run(
            [
                "remote",
                "add",
                self.image_remote_name,
                self.image_remote_addr,
                f"--protocol={self.image_remote_protocol}",
            ],
            check=True,
        )

    def _start(self) -> None:
        """Start container."""
        self._run(["start", self.instance_id], check=True)

    def _stop(self) -> None:
        """Stop container."""
        self._run(["stop", self.instance_id], check=True)

    def execute_run(self, command: List[str], **kwargs) -> subprocess.CompletedProcess:
        command = self._prepare_execute_args(command=command, kwargs=kwargs)
        return subprocess.run(command, **kwargs)

    def execute_popen(self, command: List[str], **kwargs) -> subprocess.Popen:
        command = self._prepare_execute_args(command=command, kwargs=kwargs)
        return subprocess.Popen(command, **kwargs)

    def exists(self) -> bool:
        return self._get_instance_state() is not None

    def _is_mounted(self, *, source: pathlib.Path, destination: pathlib.Path) -> bool:
        disks = [d for d in self._get_devices().values() if d.get("type") == "disk"]
        for disk in disks:
            if (
                disk.get("path") == destination.as_posix()
                and disk.get("source") == source.as_posix()
            ):
                return True
        return False

    def mount(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        """Mount host source directory to target mount point.

        Checks first to see if already mounted."""
        if self._is_mounted(source=source, destination=destination):
            return

        device_name = destination.as_posix().replace("/", "_")
        self._run(
            [
                "config",
                "device",
                "add",
                self.instance_id,
                device_name,
                "disk",
                f"source={source.as_posix()}",
                f"path={destination.as_posix()}",
            ],
            check=True,
        )

    def supports_mount(self) -> bool:
        return self.instance_remote == "local"

    def sync_from(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        logger.info(f"Syncing env:{source} -> host:{destination}...")
        # TODO: check if mount makes source == destination, skip if so.
        if naive_sync.is_target_file(executor=self, target=source):
            self._pull_file(
                source=source.as_posix(), destination=destination.as_posix()
            )
        elif naive_sync.is_target_directory(executor=self, target=source):
            # TODO: use mount() if available
            naive_sync.naive_directory_sync_from(
                executor=self, source=source, destination=destination
            )
        else:
            raise FileNotFoundError(f"Source {source} not found.")

    def sync_to(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        # TODO: check if mounted, skip sync if source == destination
        logger.info(f"Syncing host:{source} -> env:{destination}...")
        if source.is_file():
            self._push_file(
                source=source.as_posix(), destination=destination.as_posix()
            )
        elif source.is_dir():
            # TODO: use mount() if available
            naive_sync.naive_directory_sync_to(
                executor=self, source=source, destination=destination, delete=True
            )
        else:
            raise FileNotFoundError(f"Source {source} not found.")

    def setup(self) -> None:
        self._setup_image_remote()

        if self._get_instance_state() is None:
            self._launch()
        elif not self._is_instance_running():
            self._start()
