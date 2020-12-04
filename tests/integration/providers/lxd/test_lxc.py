import pathlib
import subprocess

import pytest

from xcraft.providers.lxd import LXC
from xcraft.providers.lxd.lxc import purge_project


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


def test_project_default_cfg(lxc, project):
    default_cfg = lxc.profile_show(profile="default", project="default")
    expected_cfg = default_cfg.copy()
    expected_cfg["used_by"] = []
    lxc.profile_edit(profile="default", project=project, config=default_cfg)
    updated_cfg = lxc.profile_show(profile="default", project=project)
    assert updated_cfg == expected_cfg


def test_exec(lxc, project):
    lxc.launch(
        config_keys=dict(),
        instance="t1",
        image_remote="ubuntu",
        image="16.04",
        project=project,
    )

    proc = lxc.exec(
        instance="t1",
        command=["echo", "this is a test"],
        project=project,
        capture_output=True,
    )
    assert proc.stdout == b"this is a test\n"

    instances = lxc.list(project=project)
    assert len(instances) == 1
    assert instances[0]["name"] == "t1"

    images = lxc.image_list(project=project)
    assert len(images) == 1


def test_delete_force(lxc, project):
    lxc.launch(
        config_keys=dict(),
        instance="t1",
        image_remote="ubuntu",
        image="16.04",
        project=project,
    )

    instances = lxc.list(project=project)
    assert len(instances) == 1
    assert instances[0]["name"] == "t1"

    lxc.delete(instance="t1", force=True, project=project)

    instances = lxc.list(project=project)
    assert instances == []


def test_delete_no_force(lxc, project):
    lxc.launch(
        config_keys=dict(),
        instance="t1",
        image_remote="ubuntu",
        image="16.04",
        project=project,
        ephemeral=False,
    )

    with pytest.raises(subprocess.CalledProcessError):
        lxc.delete(instance="t1", force=False, project=project)

    lxc.stop(instance="t1", project=project)

    lxc.delete(instance="t1", force=False, project=project)


def test_image_copy(lxc, project):
    lxc.image_copy(
        image="16.04",
        image_remote="ubuntu",
        alias="test-1604",
        project=project,
    )

    images = lxc.image_list(project=project)
    assert len(images) == 1


def test_image_delete(lxc, project):
    lxc.image_copy(
        image="16.04",
        image_remote="ubuntu",
        alias="test-1604",
        project=project,
    )

    lxc.image_delete(image="test-1604", project=project)

    images = lxc.image_list(project=project)
    assert images == []
