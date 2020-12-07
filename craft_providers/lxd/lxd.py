import logging
import pathlib
import shutil
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class LXD:
    """LXD Interface."""

    def __init__(
        self,
        *,
        lxd_path: Optional[pathlib.Path] = None,
    ):
        if lxd_path is None:
            self.lxd_path = self._find_lxd()
        else:
            self.lxd_path = lxd_path

    def _verify_lxd_version(self) -> None:
        proc = subprocess.run(
            [self.lxd_path, "version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        version = float(proc.stdout)
        if version < 4.8:
            raise RuntimeError(
                "LXD version {version!r} is unsupported. Must be >= 4.8."
            )

    def _find_lxd(self) -> pathlib.Path:
        lxd_path = shutil.which("lxd")

        # Default to standard snap location if not found in PATH.
        if lxd_path is None:
            lxd_path = "/snap/bin/lxd"

        return pathlib.Path(lxd_path)

    def setup(self) -> None:
        """Ensure LXD is installed with required version."""
        if not self.lxd_path.exists():
            subprocess.run(["sudo", "snap", "install", "lxd"], check=True)

            # Make sure lxd is found in PATH.
            self.lxd_path = self._find_lxd()
            if not self.lxd_path.exists():
                raise RuntimeError("Failed to install LXD, or lxd not found in PATH.")

            subprocess.run(
                ["sudo", str(self.lxd_path), "waitready", "--timeout=30"], check=True
            )
            subprocess.run(["sudo", str(self.lxd_path), "init", "--auto"], check=True)

        self._verify_lxd_version()
