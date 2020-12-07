import pathlib
import shutil
from typing import Optional


def which(command: str) -> Optional[pathlib.Path]:
    """A pathlib.Path wrapper for shutil.which()."""
    path = shutil.which(command)
    if path:
        return pathlib.Path(path)

    return None


def which_required(command: str) -> pathlib.Path:
    path = which(command)
    if path is None:
        raise RuntimeError(f"Missing required command {command!r}.")
    return path
