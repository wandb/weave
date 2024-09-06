import pytest

import weave
from weave.legacy.weave import (
    artifact_fs,
    artifact_local,
    environment,
    errors,
    storage,
    wandb_api,
)


@pytest.fixture()
def public_env():
    orig_is_public = environment.is_public
    environment.is_public = lambda: True
    token = wandb_api.set_wandb_api_context("test-user-id", None, None, None)
    try:
        yield
    finally:
        environment.is_public = orig_is_public
        wandb_api.reset_wandb_api_context(token)


def test_access_file(public_env):
    with pytest.raises(errors.WeaveAccessDeniedError):
        weave.use(weave.legacy.weave.ops.local_path("/tmp/bad.json"))


@pytest.mark.parametrize("path", ["..", "/tmp", "//tmp", "//tmp/bad.json", "/tmp/.../"])
def test_access_artifact(public_env, path):
    ref = storage.save(5)
    with pytest.raises(errors.WeaveAccessDeniedError):
        info = ref.artifact.path_info(path)

    info = artifact_fs.FilesystemArtifactFile(ref.artifact, path)
    with pytest.raises((errors.WeaveAccessDeniedError, IsADirectoryError)):
        with info.open() as f:
            pass

    art = artifact_local.LocalArtifact("test-artifact", None)
    with pytest.raises(errors.WeaveAccessDeniedError):
        with art.new_dir(path) as d:
            pass

    with pytest.raises((errors.WeaveAccessDeniedError, IsADirectoryError)):
        with art.new_file(path) as d:
            pass
