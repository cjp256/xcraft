import logging
import os
import pathlib
import shlex
import subprocess
from typing import Any, Dict, List, Optional

import yaml

from . import naive_sync
from .executor import Executor

logger = logging.getLogger(__name__)


class LXDCliExecutor(Executor):
    """Manage LXD Execution environment."""

    def __init__(
        self,
        *,
        interactive: bool = True,
        image_name: str = "20.04",
        image_remote_addr: str = "https://cloud-images.ubuntu.com/buildd/releases",
        image_remote_name: str = "snapcraft-buildd-images",
        image_remote_protocol: str = "simplestreams",
        create_ephemeral_instance: bool = False,
        instance_name: str,
        instance_remote: str = "local",
        lxc_path: Optional[pathlib.Path] = None,
    ):
        super().__init__(interactive=interactive)

        self.image_name = image_name
        self.image_remote_addr = image_remote_addr
        self.image_remote_name = image_remote_name
        self.image_remote_protocol = image_remote_protocol
        self.instance_name = instance_name
        self.instance_remote = instance_remote
        self.lxc_path = lxc_path
        self.instance_id = self.instance_remote + ":" + self.instance_name

    def _configure_instance_mknod(self) -> None:
        """Enable mknod in container, if possible.

        See: https://linuxcontainers.org/lxd/docs/master/syscall-interception
        """
        cfg = self._get_server_config()
        env = cfg.get("environment", dict())
        kernel_features = env.get("kernel_features", dict())
        seccomp_listener = kernel_features.get("seccomp_listener", "false")

        if seccomp_listener == "true":
            self._set_config_key(
                key="security.syscalls.intercept.mknod",
                value="true",
            )

    def _configure_instance_uid_mappings(self) -> None:
        """Map specified uid on host to root in container."""
        uid = os.getuid()
        self._set_config_key(
            key="raw.idmap",
            value=f"both {uid!s} 0",
        )

    def _delete(self) -> None:
        self._run(["delete", self.instance_id, "--force"], check=True)

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
            ["remote", "list", "--format=yaml"],
            stdout=subprocess.PIPE,
            check=True,
        )
        return yaml.load(proc.stdout, Loader=yaml.FullLoader)

    def _get_server_config(self) -> Dict[str, Any]:
        """Get server config that instance is running on."""
        proc = self._run(
            ["info", self.instance_remote + ":"],
            stdout=subprocess.PIPE,
            check=True,
        )
        return yaml.load(proc.stdout, Loader=yaml.FullLoader)

    def _is_instance_running(self) -> bool:
        """Check if instance is running."""
        instance_state = self._get_instance_state()
        if instance_state is None:
            return False

        return instance_state["status"] == "Running"

    def _launch(self) -> None:
        image = ":".join([self.image_remote_name, self.image_name])

        self._run(
            ["launch", image, self.instance_id],
            check=True,
        )

    def _mount(self, source: str, destination: str) -> None:
        """Mount host source directory to target mount point."""
        device_name = destination.replace("/", "_")
        self._run(
            [
                "config",
                "device",
                "add",
                self.instance_id,
                device_name,
                f"source={source}",
                f"path={destination}",
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
        env = kwargs.pop("env", dict())
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
            ["file", "pull", self.instance_id + source, destination],
            check=True,
        )

    def _push_file(self, *, source: str, destination: str) -> None:
        """Push file to instance."""
        self._run(
            ["file", "push", source, self.instance_id + destination],
            check=True,
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

    def clean(self) -> None:
        """Purge instance."""
        self._delete()

    def execute_run(self, command: List[str], **kwargs) -> subprocess.CompletedProcess:
        command = self._prepare_execute_args(command=command, kwargs=kwargs)
        return subprocess.run(command, **kwargs)

    def execute_popen(self, command: List[str], **kwargs) -> subprocess.Popen:
        command = self._prepare_execute_args(command=command, kwargs=kwargs)
        return subprocess.Popen(command, **kwargs)

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

        self._configure_instance_mknod()
        self._configure_instance_uid_mappings()

    def teardown(self) -> None:
        self._stop()
