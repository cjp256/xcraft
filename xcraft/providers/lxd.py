import logging
import pathlib
import shlex
import subprocess
from typing import Any, Dict, List, Optional

from xcraft.executors import LXDExecutor

from .provider import Provider

logger = logging.getLogger(__name__)


class LXDProvider(Provider):
    """Base LXD Provider.

    This should be subclassed and extended for each project.

    """

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
        lxd_path: Optional[pathlib.Path] = None,
    ):
        super().__init__(interactive=interactive)

        self.executor = LXDExecutor(
            interactive=interactive,
            image_name=image_name,
            image_remote_addr=image_remote_addr,
            image_remote_name=image_remote_name,
            image_remote_protocol=image_remote_protocol,
            create_ephemeral_instance=create_ephemeral_instance,
            instance_name=instance_name,
            instance_remote=instance_remote,
        )

    def _setup_lxd(self) -> None:
        """Ensure LXD is installed with required version."""
        if self.lxd_path:
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
            return

        subprocess.run(["sudo", "snap", "install", "lxd"], check=True)

        # Update paths after installing.
        if not self._find_executables():
            raise RuntimeError("Cannot find lxc or lxd executables.")

        subprocess.run(["sudo", self.lxd_path, "waitready", "--timeout=30"], check=True)
        subprocess.run(["sudo", self.lxd_path, "init", "--auto"], check=True)

    def _prepare_instance(self) -> None:
        # Setup networking, if required by image (e.g. buildd).
        # Install snapd, if required by image, etc. etc.
        self.execute_run(["apt", "update"])
        self.execute_run(["apt", "install", "-y", "snapd", "sudo"])

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

    def setup(self) -> None:
        self._setup_lxd()
        self.executor.__enter__()
        self._prepare_instance()

    def teardown(self) -> None:
        self.executor.teardown()
