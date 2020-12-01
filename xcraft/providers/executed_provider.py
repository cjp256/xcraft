import base64
import logging
import os
import pathlib
import tempfile
from typing import Dict

from xcraft.executors.executor import Executor

from .provider import Provider

logger = logging.getLogger(__name__)


class ExecutedProvider(Provider):
    """Guarantees availability of executor and provides common helper methods."""

    def __init__(
        self,
        *,
        interactive: bool,
        executor: Executor,
        default_run_environment: Dict[str, str],
        **kwargs
    ) -> None:
        super().__init__(interactive=interactive, **kwargs)

        self.executor = executor

        self.default_run_environment = default_run_environment

    def _install_file(self, *, path: str, content: str, permissions: str) -> None:
        """Install file into target with specified content and permissions."""
        basename = os.path.basename(path)

        # Push to a location that can be written to by all backends
        # with unique files depending on path.
        # The path should be a valid path for the target.
        remote_file = "/var/tmp/{}".format(base64.b64encode(path.encode()).decode())

        # Windows cannot open the same file twice, so write to a temporary file that
        # would later be deleted manually.
        with tempfile.NamedTemporaryFile(delete=False, suffix=basename) as temp_file:
            temp_file.write(content.encode())
            temp_file.flush()
            temp_file_path = temp_file.name

        try:
            self.executor.sync_to(
                source=pathlib.Path(temp_file.name),
                destination=pathlib.Path(remote_file),
            )
            self.executor.execute_run(["mv", remote_file, path])

            # This chown is not necessarily needed. but does keep things
            # consistent.
            self.executor.execute_run(["chown", "root:root", path])
            self.executor.execute_run(["chmod", permissions, path])
        finally:
            os.unlink(temp_file_path)
