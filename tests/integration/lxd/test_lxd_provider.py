import subprocess

import pytest

from craft_providers.images import BuilddImage, BuilddImageAlias
from craft_providers.lxd import LXDInstance, LXDProvider


@pytest.mark.parametrize(
    "alias", [BuilddImageAlias.XENIAL, BuilddImageAlias.BIONIC, BuilddImageAlias.FOCAL]
)
@pytest.mark.parametrize("use_ephemeral_instances", [False, True])
@pytest.mark.parametrize("use_intermediate_image", [False, True])
def test_lxd_provider(
    lxc, project, alias, use_ephemeral_instances, use_intermediate_image
):
    image = BuilddImage(alias=alias)
    provider = LXDProvider(
        instance_name="test1",
        image=image,
        image_remote_addr="https://cloud-images.ubuntu.com/buildd/releases",
        image_remote_name="ubuntu",
        image_remote_protocol="simplestreams",
        lxc=lxc,
        use_ephemeral_instances=use_ephemeral_instances,
        use_intermediate_image=use_intermediate_image,
        project=project,
        remote="local",
    )

    instance = provider.setup()

    assert isinstance(instance, LXDInstance)
    assert instance.exists() is True
    assert instance.is_running() is True

    proc = instance.execute_run(["echo", "hi"], check=True, stdout=subprocess.PIPE)

    assert proc.stdout == b"hi\n"

    provider.teardown(clean=False)

    assert instance.exists() is not use_ephemeral_instances
    assert instance.is_running() is False

    provider.teardown(clean=True)

    assert instance.exists() is False
    assert instance.is_running() is False
