import subprocess
import pathlib
import pytest
import contextlib
from xcraft.providers.lxd import LXC

def run(cmd, **kwargs):
    return subprocess.run(
        cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, check=True, **kwargs
    )

@pytest.fixture(scope="module")
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

@pytest.fixture(scope="module")
def lxc(lxd):
    yield LXC()

@pytest.fixture(scope="module")
def project(lxc):
    name = "xcraft-test-project"
    with contextlib.suppress(subprocess.CalledProcessError):
        lxc.project_delete(name=name)
    yield name

@pytest.mark.incremental
class TestLXC:
    def test_project_create(self, lxc, project):
        lxc.project_create(name=project)
    
    def test_project_list(self, lxc, project):
        projects = lxc.project_list()
        project_names = [p["name"] for p in projects]

        assert project in project_names

    def test_list_empty(self, lxc, project):
        instances = lxc.list(project=project)

        assert instances == []

    def test_profile_show(self, lxc, project):
        cfg = lxc.profile_show(name="default", project=project)

        assert cfg == {'config': {}, 'description': 'Default LXD profile for project xcraft-test-project', 'devices': {}, 'name': 'default', 'used_by': []}

    def test_profile_edit(self, lxc, project):
        default_cfg = lxc.profile_show(name="default", project="default")
        lxc.profile_edit(name="default", project="default", config=default_cfg)

        cfg = lxc.profile_show(name="default", project=project)

        assert cfg == default_cfg

    def test_launch(self, lxc, project):
        lxc.launch(config_keys=dict(), instance_id="local:t1", image_remote="ubuntu", image_name="16.04", project=project)



        

