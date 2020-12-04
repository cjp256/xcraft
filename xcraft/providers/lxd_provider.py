import logging
from typing import Optional

from .executed_provider import ExecutedProvider
from .lxd import LXC, LXD, LXDInstance

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
        self.project = project
        self.remote = remote

    def setup(self) -> LXDInstance:
        self.lxd.setup()
        self.lxc.setup()
        self._setup_image_remote()
        return self._setup_instance()

    def _setup_image_remote(self) -> None:
        """Add a public remote."""
        remotes = self.lxc.remote_list()
        remote = remotes.get(self.image_remote_name)

        # Ensure remote configuration matches.
        if (
            remote is not None
            and remote.get("addr") != self.image_remote_addr
            and remote.get("protocol") != self.image_remote_protocol
        ):
            raise RuntimeError(
                f"Remote configuration does not match for {self.remote!r}."
            )

        self.lxc.remote_add(
            remote=self.image_remote_name,
            addr=self.image_remote_addr,
            protocol=self.image_remote_protocol,
        )

    def _setup_instance(self) -> LXDInstance:
        if self.instance is None:
            self.instance = LXDInstance(
                name=self.instance_name,
                image=self.image,
                project=self.project,
                remote=self.remote,
                lxc=self.lxc,
            )

        if self.instance.exists():
            if not self.instance.is_running():
                self.instance.start()
            # TODO: add verififcation that instance matches
        else:
            self.instance.launch(
                image=self.image,
                image_remote=self.image_remote_name,
                ephemeral=self.use_ephemeral_instances,
            )

        self.instance.setup()
        return self.instance

    def teardown(self, *, clean: bool = False) -> None:
        if self.instance is None:
            return

        if self.instance.is_running():
            self.instance.stop()

        if clean:
            self.instance.delete(force=True)
