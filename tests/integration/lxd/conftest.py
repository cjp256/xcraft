import pathlib
import subprocess

import pytest

from craft_providers.lxd import LXC
from craft_providers.lxd.lxc import purge_project


def run(cmd, **kwargs):
    return subprocess.run(
        cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, check=True, **kwargs
    )


@pytest.fixture()
def lxd():
    lxc_path = pathlib.Path("/snap/bin/lxc")
    if lxc_path.exists():
        already_installed = True
    else:
        already_installed = False
        run(["sudo", "snap", "install", "lxd"])

    yield lxc_path

    if not already_installed:
        run(["sudo", "snap", "remove", "lxd"])


@pytest.fixture()
def lxc(lxd):
    yield LXC()


@pytest.fixture()
def project(lxc):
    project = "xcraft-test-project"
    purge_project(lxc=lxc, project=project)

    lxc.project_create(project=project)

    default_cfg = lxc.profile_show(profile="default", project="default")
    lxc.profile_edit(profile="default", project=project, config=default_cfg)

    projects = lxc.project_list()
    assert project in projects

    instances = lxc.list(project=project)
    assert instances == []

    yield project

    purge_project(lxc=lxc, project=project)


@pytest.fixture()
def instance(lxc, project):
    instance = "t1"
    lxc.launch(
        config_keys=dict(),
        instance=instance,
        image_remote="ubuntu",
        image="16.04",
        project=project,
    )

    yield instance

    lxc.delete(instance=instance, project=project)
