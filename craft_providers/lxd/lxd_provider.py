import logging
from typing import Optional

from ..executed_provider import ExecutedProvider
from . import LXC, LXD, LXDInstance

logger = logging.getLogger(__name__)


class LXDProvider(ExecutedProvider):
    """Base LXD Provider.

    This should be subclassed and extended for each project.

    """

    def __init__(
        self,
        *,
        instance_name: str,
        image: str = "20.04",
        image_remote_addr: str = "https://cloud-images.ubuntu.com/buildd/releases",
        image_remote_name: str = "snapcraft-buildd-images",
        image_remote_protocol: str = "simplestreams",
        instance: Optional[LXDInstance] = None,
        lxc: Optional[LXC] = None,
        lxd: Optional[LXD] = None,
        use_ephemeral_instances: bool = True,
        use_intermediate_image: bool = True,
        project: str = "default",
        remote: str = "local",
    ):
        self.image = image
        self.instance = instance
        self.instance_name = instance_name
        self.image_remote_addr = image_remote_addr
        self.image_remote_name = image_remote_name
        self.image_remote_protocol = image_remote_protocol

        if lxc is None:
            self.lxc = LXC()
        else:
            self.lxc = lxc

        if lxd is None:
            self.lxd = LXD()
        else:
            self.lxd = lxd

        self.use_ephemeral_instances = use_ephemeral_instances
        self.use_intermediate_image = use_intermediate_image
        self.project = project
        self.remote = remote

    def setup(self) -> LXDInstance:
        self.lxd.setup()
        self.lxc.setup()
        self._setup_image_remote()

        if self.use_intermediate_image:
            intermediate_image = self._setup_intermediate_image()
            return self._setup_instance(
                instance=self.instance_name,
                image=intermediate_image,
                image_remote=self.remote,
            )
        else:
            return self._setup_instance(
                instance=self.instance_name,
                image=self.image,
                image_remote=self.image_remote_name,
            )

    def _setup_image_remote(self) -> None:
        """Add a public remote."""
        remotes = self.lxc.remote_list()
        remote = remotes.get(self.image_remote_name)

        # Ensure remote configuration matches.
        if remote is not None:
            if (
                remote.get("addr") != self.image_remote_addr
                and remote.get("protocol") != self.image_remote_protocol
            ):
                raise RuntimeError(
                    f"Remote configuration does not match for {self.remote!r}."
                )
            return

        self.lxc.remote_add(
            remote=self.image_remote_name,
            addr=self.image_remote_addr,
            protocol=self.image_remote_protocol,
        )

    def _setup_instance(
        self, *, instance: str, image: str, image_remote: str
    ) -> LXDInstance:
        lxd_instance = LXDInstance(
            name=instance,
            image=image,
            project=self.project,
            remote=self.remote,
            lxc=self.lxc,
        )

        if lxd_instance.exists():
            if not lxd_instance.is_running():
                lxd_instance.start()
            # TODO: add verififcation that instance matches
        else:
            lxd_instance.launch(
                image=image,
                image_remote=image_remote,
                ephemeral=self.use_ephemeral_instances,
            )

        lxd_instance.setup()
        return lxd_instance

    def _setup_intermediate_image(self) -> str:
        intermediate_name = self.image_remote_name + "-" + self.image.replace(".", "-")

        images = self.lxc.image_list(project=self.project, remote=self.remote)
        for image in images:
            for alias in image["aliases"]:
                if intermediate_name == alias["name"]:
                    logger.info("Using intermediate image.")
                    return intermediate_name

        intermediate_instance = self._setup_instance(
            instance=intermediate_name,
            image=self.image,
            image_remote=self.image_remote_name,
        )

        # Publish intermediate image.
        self.lxc.publish(
            alias=intermediate_name,
            instance=intermediate_name,
            project=self.project,
            remote=self.remote,
        )

        # Nuke it.
        intermediate_instance.delete(force=True)
        return intermediate_name

    def _setup_project(self) -> None:
        projects = self.lxc.project_list(remote=self.remote)
        if self.project in projects:
            return

    def teardown(self, *, clean: bool = False) -> None:
        if self.instance is None:
            return

        if self.instance.is_running():
            self.instance.stop()

        if clean:
            self.instance.delete(force=True)
