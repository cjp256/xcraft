class LifecycleManager:
    """Manages the lifecycle of a project."""

    def __enter__(self) -> "LifecycleManager":
        pass

    def __exit__(self) -> None:
        pass

    def execute_step(self, step: step.Step, part_name: Optional[List[str]]) -> None:
        """Execute (up to, and including) specified step.

        :param step: Step to execute.
        :param part_names: Optional list of part names to execute step for.

        :raises SnapcraftProviderUnsupportedMethod: if provider does not support
            executing steps.
        """

    def expose_prime(self, prime_dir: pathlib.Path) -> None:
        """Make project's prime directory available to host's prime_dir.

        Implementations should use the most performant approach available
        for the given provider (i.e. bind mounting directory from container).

        :param prime_dir: Directory to mount/sync prime directory to on host.

        :raises SnapcraftProviderUnsupportedMethod: if provider does not support
            syncing/mounting project's prime directory.
        """

    def snap(self, output_dir: pathlib.Path) -> List[pathlib.Path]:
        """Snap project, executing lifecycle steps as required.

        Write output snaps to host project directory.

        :param output_dir: Directory to write snaps to.

        :returns: Path to snap(s) created from build.
        """

    def clean_parts(self, part_names: List[str]) -> None:
        """Clean specified parts.

        :param part_names: List of parts to clean.

        :raises SnapcraftProviderUnsupportedMethod: if provider does not support
            executing steps.
        """

    def clean(self) -> None:
        """Clean all artifacts of project and build environment.

        Purges all artifacts from using the provider to build the
        project.  This includes build-instances (containers/VMs) and
        associated metadata and records.

        This does not include any artifacts that have resulted from
        a call to snap(), i.e. snap files or build logs.
        """

    def shell(self, step: Optional[step.Step], part_name: Optional[str]) -> None:
        """Launch an interactive shell to build-instance.

        If available, load environment used for the given step and part_name.
        Step and part_name must both be supplied for environment to be loaded,
        otherwise both are ignored.

        Note this method does not imply execute_step(), it is up to the caller
        to launch the shell at the appropriate time.

        :param step: step to load environment for.
        :param part_name: part_name to load environment for.  If step is specified,
            but not a part_name.

        :raises SnapcraftProviderUnsupportedMethod: if provider does not support
            providing a shell.
        """
