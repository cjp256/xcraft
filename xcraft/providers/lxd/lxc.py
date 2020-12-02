import logging
import pathlib
import shlex
import subprocess
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class LXC:
    """Wrapper for lxc."""

    def __init__(
        self, *, lxc_path: pathlib.Path = pathlib.Path("/snap/bin/lxc"),
    ):
        if lxc_path is None:
            self.lxc_path = pathlib.Path("lxc")
        else:
            self.lxc_path = lxc_path

    def _run(
        self,
        *,
        command: List[str],
        project: str = "default",
        check=True,
        input=None,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ) -> subprocess.CompletedProcess:
        """Execute command in instance, allowing output to console."""
        command = [str(self.lxc_path), "--project", project, *command]
        quoted = " ".join([shlex.quote(c) for c in command])

        logger.info(f"Executing on host: {quoted}")

        try:
            proc = subprocess.run(
                command, check=check, input=input, stderr=stderr, stdin=stdin, stdout=stdout
            )
        except subprocess.CalledProcessError as error:
            logger.info(f"Failed to execute: {error.output}")
            raise error

        return proc

    def config_device_add(
        self,
        *,
        instance_id: str,
        source: pathlib.Path,
        destination: pathlib.Path,
        device_name: Optional[str],
        project: str = "default",
    ) -> None:
        """Mount host source directory to target mount point."""
        if device_name is None:
            device_name = destination.as_posix().replace("/", "_")

        self._run(
            command=[
                "config",
                "device",
                "add",
                instance_id,
                device_name,
                "disk",
                f"source={source.as_posix()}",
                f"path={destination.as_posix()}",
            ],
            project=project,
        )

    def config_device_show(
        self, *, instance_id: str, project: str = "default"
    ) -> Dict[str, Any]:
        proc = self._run(
            command=["config", "device", "show", instance_id], project=project,
        )

        return yaml.load(proc.stdout, Loader=yaml.FullLoader)

    def config_set(
        self, *, instance_id: str, key: str, value: str, project: str = "default"
    ) -> None:
        """Set instance configuration key."""
        self._run(command=["config", "set", instance_id, key, value], project=project)

    def delete(self, *, instance_id: str, project: str = "default") -> None:
        """Delete instance."""
        self._run(command=["delete", instance_id, "--force"], project=project)

    def execute_command(
        self,
        *,
        command: List[str],
        instance_id: str,
        cwd: str = "/root",
        mode: str = "auto",
        project: str = "default",
    ) -> List[str]:
        """Formulate command to run."""
        final_cmd = [str(self.lxc_path), "--project", project, "exec", instance_id]

        if cwd != "/root":
            final_cmd.extend(["--cwd", cwd])

        if mode != "auto":
            final_cmd.extend(["--mode", mode])

        final_cmd.extend(["--", *command])

        return final_cmd

    def execute(
        self,
        *,
        command: List[str],
        instance_id: str,
        cwd: str = "/root",
        mode: str = "auto",
        project: str = "default",
        runner=subprocess.run,
        **kwargs,
    ):
        """Execute command in instance with specified runner."""
        command = self.execute_command(
            command=command,
            instance_id=instance_id,
            cwd=cwd,
            mode=mode,
            project=project,
        )

        quoted = " ".join([shlex.quote(c) for c in command])
        logger.info(f"Executing in container: {quoted}")

        return runner(command, **kwargs)

    def file_pull(
        self,
        *,
        instance_id: str,
        source: str,
        destination: str,
        project: str = "default",
    ) -> None:
        """Retrieve file from instance."""
        self._run(
            command=["file", "pull", instance_id + source, destination],
            project=project,
        )

    def file_push(
        self,
        *,
        instance_id: str,
        source: pathlib.Path,
        destination: pathlib.Path,
        gid: str = "0",
        uid: str = "0",
        file_mode: str = "0644",
        project: str = "default",
    ) -> None:
        """Create file with content and file mode."""
        self._run(
            command=[
                "file",
                "push",
                source.name,
                instance_id + destination.as_posix(),
                "--create-dirs",
                "--mode",
                file_mode,
                "--gid",
                gid,
                "--uid",
                uid,
            ],
            project=project,
        )

    def info(
        self, *, remote: str = "local", project: str = "default"
    ) -> Dict[str, Any]:
        """Get server config that instance is running on."""
        proc = self._run(command=["info", remote + ":"], project=project,)
        return yaml.load(proc.stdout, Loader=yaml.FullLoader)

    def launch(
        self,
        *,
        config_keys: Dict[str, str],
        instance_id: str,
        image_remote: str,
        image_name: str,
        project: str = "default",
    ) -> None:
        image = ":".join([image_remote, image_name])

        command = [
            "--project",
            project,
            "launch",
            image,
            instance_id,
        ]

        for config_key in [f"{k}={v}" for k, v in config_keys.items()]:
            command.extend(["--config", config_key])

        self._run(command=command, project=project)

    def list(
        self, *, project: str = "default"
    ) -> List[Dict[str, Any]]:
        """List instances."""
        proc = self._run(
            command=["list", "--format=yaml"], project=project,
        )

        return yaml.load(proc.stdout, Loader=yaml.FullLoader)

    def profile_edit(self, *, name: str, project: str = "local", config: Dict[str, Any]) -> None:
        cfg = yaml.dump(config)
        self._run(command=["profile", "edit", name], project=project, input=cfg.encode(), stdin=subprocess.PIPE)

    def profile_show(self, *, name: str, project: str = "local") -> Dict[str, Any]:
        """Get profile."""
        proc = self._run(command=["profile", "show", name], project=project)
        return yaml.load(proc.stdout, Loader=yaml.FullLoader)

    def project_create(self, *, name: str) -> None:
        """Create project."""
        self._run(command=["project", "create", name])

    def project_list(self) -> List[Dict[str, Any]]:
        """Get list of remotes.

        :returns: dictionary with remote name mapping to config.
        """
        proc = self._run(command=["project", "list", "--format=yaml"])
        return yaml.load(proc.stdout, Loader=yaml.FullLoader)

    def project_delete(self, *, name: str) -> None:
        """Delete project, if exists."""
        self._run(command=["project", "delete", name])

    def remote_add(self, *, name: str, addr: str, protocol: str) -> None:
        """Add a public remote."""
        self._run(command=["remote", "add", name, addr, f"--protocol={protocol}"])

    def remote_list(self) -> List[Dict[str, Any]]:
        """Get list of remotes.

        :returns: dictionary with remote name mapping to config.
        """
        proc = self._run(command=["remote", "list", "--format=yaml"])
        return yaml.load(proc.stdout, Loader=yaml.FullLoader)

    def start(self, *, instance_id: str, project: str = "default") -> None:
        """Start container."""
        self._run(command=["start", instance_id], project=project)

    def stop(self, *, instance_id: str, project: str = "default") -> None:
        """Stop container."""
        self._run(command=["stop", instance_id], project=project)
