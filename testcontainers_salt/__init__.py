import tempfile
from collections import defaultdict
from importlib.abc import Traversable
from os import PathLike
from pathlib import Path

import importlib.resources as resources

from typing_extensions import Literal, Self

from testcontainers.core.container import DockerContainer
from testcontainers.core.image import DockerImage
import yaml

import logging

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

logging.basicConfig(level=logging.DEBUG)


def represent_dict_with_skip_none(dumper, data):
    return dumper.represent_dict({k: v for k, v in data.items() if v is not None})


yaml.add_representer(dict, represent_dict_with_skip_none)
yaml.add_representer(defaultdict, represent_dict_with_skip_none)

# Make "env" a type alias for str
env = str

# Define salt_log_level as a literal type with possible log level values
salt_log_level = Literal[
    "garbage", "trace", "debug", "info", "warning", "error", "critical"
]


class SaltImageDocker(DockerImage):
    def __init__(self, salt_version: str = "3007", **kwargs):
        self.salt_version = salt_version
        dockerfile = (
            resources.files("testcontainers_salt") / "resources" / "Dockerfile.ubuntu"
        )
        # Pass the salt version as a build arg
        super().__init__(".", dockerfile_path=str(dockerfile), **kwargs)

    def build(self, **kwargs):
        super().build(
            buildargs={
                "SALT_VERSION": self.salt_version,
            },
            **kwargs,
        )


SaltImage = SaltImageDocker


class SaltContainer(DockerContainer):
    def __init__(self, image=None, **kwargs):
        self._id = None
        self._saltenv = None

        self.config_dir = Path("/etc/salt")
        self.base_dir_state = Path("/srv/salt")
        self.base_dir_pillar = Path("/srv/pillar")

        self.state_top: str | None = None
        self.state_top_saltenv: str | None = None

        # Contains the config paths for the file roots and pillar roots
        self.file_roots: dict[env, list[str]] = defaultdict(list)
        self.pillar_roots: dict[env, list[str]] = defaultdict(list)

        # Contains the volume mappings for the file roots and pillar roots
        self._file_root_volume_mappings: dict[
            env, list[tuple[str | PathLike, str | PathLike]]
        ] = defaultdict(list)
        self._pillar_root_volume_mappings: dict[
            env, list[tuple[str | PathLike, str | PathLike]]
        ] = defaultdict(list)

        self.file_server_backends: list[str] = []
        self.gitfs_remotes: list[str] = []
        self.state_verbose: bool = False

        self.config_file: dict = {}
        self.extra_config_data: dict = {}

        self._complete_config: dict = {}

        if image is None:
            image = SaltImage(**kwargs)
            image.build()

        super().__init__(str(image), **kwargs)

    def _configure(self) -> None:

        # Pytest Temp Dir
        config_dir = Path(tempfile.mkdtemp())

        config_file_path = config_dir / "minion"

        self.config_file["id"] = self._id
        self.config_file["saltenv"] = self._saltenv
        self.config_file["state_top"] = self.state_top
        self.config_file["state_top_saltenv"] = self.state_top_saltenv
        self.config_file["file_roots"] = self.file_roots
        self.config_file["pillar_roots"] = self.pillar_roots
        self.config_file["file_server_backends"] = self.file_server_backends
        self.config_file["gitfs_remotes"] = self.gitfs_remotes
        self.config_file["state_verbose"] = self.state_verbose
        self.config_file["log_level"]: salt_log_level = "debug"
        self.config_file["log_level_logfile"]: salt_log_level = "debug"
        self._complete_config = self.config_file | self.extra_config_data

        with open(config_file_path, "w") as f:
            # Dump to YAML, but only with basic
            output = yaml.dump(self._complete_config, default_flow_style=False)
            log.debug(output)
            f.write(output)

        # Mapped this way so that we can still mount the config dir if we want to
        self.with_volume_mapping(str(config_file_path), str(self.config_dir / "minion"))

        # Mount all the file roots
        for environ, file_roots in self._file_root_volume_mappings.items():
            log.debug(f"environ: {environ}, file_roots: {file_roots}")
            if environ == "__env__":
                continue

            for host_path, target_path in file_roots:
                log.debug(f"host_path: {host_path}, target_path: {target_path}")

                if "__env__" in str(target_path):
                    continue

                self.with_volume_mapping(
                    str(host_path), str(self.base_dir_state / environ / target_path)
                )

        # Mount all the pillar roots
        for environ, pillar_roots in self._pillar_root_volume_mappings.items():
            log.debug(f"environ: {environ}, pillar_roots: {pillar_roots}")
            if environ == "__env__":
                continue

            for host_path, target_path in pillar_roots:
                if "__env__" in str(host_path):
                    continue

                log.debug(f"host_path: {host_path}, target_path: {target_path}")
                self.with_volume_mapping(
                    str(host_path), str(self.base_dir_pillar / environ / target_path)
                )

    def with_id(self, id: str) -> Self:
        self._id = id
        return self

    def with_saltenv(self, saltenv: str) -> Self:
        self._saltenv = saltenv
        return self

    def with_file_root(
        self,
        host_path: str | PathLike | Traversable,
        target_path: str | PathLike | Traversable,
        environ: env = "base",
    ) -> Self:

        # Resolve the host path to an absolute path
        host_path = Path(host_path).resolve()
        # Resolve the target path to an absolute path
        target_path = (self.base_dir_state / Path(target_path)).resolve()

        # Simply fixes the config
        self.file_roots[environ].append(str(target_path))

        # Maps the host path to the target path
        self._file_root_volume_mappings[environ].append((host_path, target_path))
        return self

    def with_pillar_root(
        self,
        host_path: str | PathLike | Traversable,
        target_path: str | PathLike | Traversable,
        environ: env = "base",
    ) -> Self:
        host_path = Path(host_path).resolve()
        target_path = (self.base_dir_pillar / Path(target_path)).resolve()

        self.pillar_roots[environ].append(str(target_path))
        self._pillar_root_volume_mappings[environ].append((host_path, target_path))
        return self

    def with_config_file(self, path: str | PathLike) -> Self:
        self.config_file = yaml.safe_load(open(path))
        return self

    def with_file_server_backend(self, backend: str) -> Self:
        self.file_server_backends.append(backend)
        return self

    def with_gitfs_remote(self, remote: str) -> Self:
        self.gitfs_remotes.append(remote)
        return self

    def with_state_verbose(self, verbose: bool = True) -> Self:
        self.state_verbose = verbose
        return self

    def with_state_top(self, path: str) -> Self:
        self.state_top = path
        return self

    def with_state_top_saltenv(self, saltenv: str) -> Self:
        self.state_top_saltenv = saltenv
        return self

    def with_extra_config(self, config: dict) -> Self:
        self.extra_config_data = config
        return self

    def with_log_level(self, log_level: salt_log_level) -> Self:
        self.log_level = log_level

    def with_log_level_logfile(self, log_level: salt_log_level) -> Self:
        self.log_level_logfile = log_level

    def get_salt_call_args(
        self, command: str = "state.apply", output: str = "yaml"
    ) -> list[str]:
        return [
            "salt-call",
            "--local",
            f"--config-dir={self.config_dir}",
            f"--id={self._id}",
            f"--out={output}",
            f"{command}",
        ]

    def exec_salt_call(self, command: str = "state.apply") -> tuple[int, bytes]:
        return self.exec(self.get_salt_call_args(command))
