from pathlib import Path

import pytest

from testcontainers_salt import SaltContainer
import testinfra

@pytest.fixture(scope="module")
def container_fixture():
    # Find the salt_files directory relative to the current file
    salt_files_dir = Path(__file__).parent / "resources" / "salt_files"
    state_root = salt_files_dir / "salt"
    pillar_root = salt_files_dir / "pillar"

    container = (
        SaltContainer(salt_version="3007")
        .with_file_root(state_root / "base", "base", environ="__env__")
        .with_file_root(state_root / "__env__", "__env__", environ="__env__")
        .with_file_root(state_root / "base", "base", environ="base")
        .with_pillar_root(pillar_root / "base", "base", environ="__env__")
        .with_pillar_root(pillar_root / "__env__", "__env__", environ="__env__")
        .with_pillar_root(pillar_root / "base", "base", environ="base")
        .with_file_server_backend("gitfs")
        .with_file_server_backend("roots")
        .with_gitfs_remote("https://github.com/saltstack-formulas/apache-formula")
        .with_state_verbose()
    )

    container.start()

    # Run salt-call
    result = container.exec(
        [
            "salt-call",
            "--local",
            f"--config-dir={container.config_dir}",
            f"--id=httpd_test",
            "state.apply",
        ]
    )
    result = result.output.decode("utf-8")

    print(result)

    yield container
    container.stop()
@pytest.fixture(scope="module")
def host(container_fixture: SaltContainer):
    conatiner_id = container_fixture.get_wrapped_container().id
    return testinfra.get_host(f"docker://{conatiner_id}")

def test_container(container_fixture):
    result = container_fixture.exec(["cat", "/etc/salt/minion"])
    print(result)

def test_passwd(host):
    passwd = host.file("/etc/passwd")
    assert passwd.contains("root")
    assert passwd.user == "root"
    assert passwd.group == "root"
    assert passwd.mode == 0o644