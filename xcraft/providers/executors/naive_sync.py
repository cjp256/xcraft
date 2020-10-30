import logging
import pathlib
import shutil
import subprocess

from xcraft.util import path

from .provider import Provider

logger = logging.getLogger(__name__)


def is_target_directory(*, provider: Provider, target: pathlib.Path) -> bool:
    proc = provider.execute_run(command=["test", "-d", target.as_posix()])
    return proc.returncode == 0


def is_target_file(*, provider: Provider, target: pathlib.Path) -> bool:
    proc = provider.execute_run(command=["test", "-f", target.as_posix()])
    return proc.returncode == 0


def naive_directory_sync_from(
    *, provider: Provider, source: pathlib.Path, destination: pathlib.Path
) -> None:
    """Naive sync from remote using tarball.

    Relies on only the required Provider interfaces.
    """
    logger.info(f"Syncing {source}->{destination} to host...")
    destination_path = destination.as_posix()

    if destination.exists():
        shutil.rmtree(destination)
        destination.mkdir(parents=True)

    tar_path = path.which_required(command="tar")

    archive_proc = subprocess.Popen(
        [tar_path, "cpf", "-", "-C", source, "."],
        stdout=subprocess.PIPE,
    )

    target_proc = provider.execute_popen(
        ["tar", "xpvf", "-", "-C", destination_path],
        stdin=archive_proc.stdout,
    )

    # Allow archive_proc to receive a SIGPIPE if destination_proc exits.
    if archive_proc.stdout:
        archive_proc.stdout.close()

    # Waot until done.
    target_proc.communicate()


def _naive_directory_sync_to(
    *, provider: Provider, source: pathlib.Path, destination: pathlib.Path
) -> None:
    """Naive sync to remote using tarball.

    Relies on only the required Provider interfaces.
    """
    logger.info(f"Syncing {source}->{destination} to build environment...")
    destination_path = destination.as_posix()

    provider.execute_run(["rm", "-rf", destination_path], check=True)
    provider.execute_run(["mkdir", "-p", destination_path], check=True)

    tar_path = path.which_required(command="tar")

    archive_proc = subprocess.Popen(
        [tar_path, "cpf", "-", "-C", source, "."],
        stdout=subprocess.PIPE,
    )

    target_proc = provider.execute_popen(
        ["tar", "xpvf", "-", "-C", destination_path],
        stdin=archive_proc.stdout,
    )

    # Allow archive_proc to receive a SIGPIPE if destination_proc exits.
    if archive_proc.stdout:
        archive_proc.stdout.close()

    # Waot until done.
    target_proc.communicate()
