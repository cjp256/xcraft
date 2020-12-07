from craft_providers.lxd import LXDInstance, LXDProvider


def test_lxd_provider(lxc, project):
    provider = LXDProvider(
        instance_name="test1",
        image="20.04",
        image_remote_addr="https://cloud-images.ubuntu.com/buildd/releases",
        image_remote_name="ubuntu",
        image_remote_protocol="simplestreams",
        instance=None,
        lxc=lxc,
        use_ephemeral_instances=False,
        use_intermediate_image=False,
        project=project,
        remote="local",
    )

    instance = provider.setup()

    assert isinstance(instance, LXDInstance)
