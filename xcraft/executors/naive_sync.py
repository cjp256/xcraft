import logging
import pathlib
import shutil
import subprocess

from xcraft.executors.executor import Executor
from xcraft.util import path

logger = logging.getLogger(__name__)


def is_target_directory(*, executor: Executor, target: pathlib.Path) -> bool:
    proc = executor.execute_run(command=["test", "-d", target.as_posix()])
    return proc.returncode == 0


def is_target_file(*, executor: Executor, target: pathlib.Path) -> bool:
    proc = executor.execute_run(command=["test", "-f", target.as_posix()])
    return proc.returncode == 0


def naive_directory_sync_from(
    *, executor: Executor, source: pathlib.Path, destination: pathlib.Path
) -> None:
    """Naive sync from remote using tarball.

    Relies on only the required Executor.interfaces.
    """
    logger.info(f"Syncing {source}->{destination} to host...")
    destination_path = destination.as_posix()

    if destination.exists():
        shutil.rmtree(destination)
        destination.mkdir(parents=True)

    tar_path = path.which_required(command="tar")

    archive_proc = executor.execute_popen(
        [tar_path, "cpf", "-", "-C", source.as_posix(), "."],
        stdout=subprocess.PIPE,
    )

    target_proc = subprocess.Popen(
        ["tar", "xpvf", "-", "-C", str(destination)],
        stdin=archive_proc.stdout,
    )

    # Allow archive_proc to receive a SIGPIPE if destination_proc exits.
    if archive_proc.stdout:
        archive_proc.stdout.close()

    # Waot until done.
    target_proc.communicate()


def naive_directory_sync_to(
    *, executor: Executor, source: pathlib.Path, destination: pathlib.Path, delete=True
) -> None:
    """Naive sync to remote using tarball.

    Relies on only the required Executor.interfaces.
    """
    logger.info(f"Syncing {source}->{destination} to build environment...")
    destination_path = destination.as_posix()

    if delete is True:
        executor.execute_run(["rm", "-rf", destination_path], check=True)

    executor.execute_run(["mkdir", "-p", destination_path], check=True)

    tar_path = path.which_required(command="tar")

    archive_proc = subprocess.Popen(
        [tar_path, "cpf", "-", "-C", str(source), "."],
        stdout=subprocess.PIPE,
    )

    target_proc = executor.execute_popen(
        ["tar", "xpvf", "-", "-C", destination_path.as_posix()],
        stdin=archive_proc.stdout,
    )

    # Allow archive_proc to receive a SIGPIPE if destination_proc exits.
    if archive_proc.stdout:
        archive_proc.stdout.close()

    # Waot until done.
    target_proc.communicate()
