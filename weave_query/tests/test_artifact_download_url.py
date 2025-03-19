import pytest
from weave_query.wandb_file_manager import _local_path_and_download_url
from weave_query.artifact_wandb import WeaveWBArtifactURI, WeaveWBArtifactByIDURI, WandbArtifactManifest
from wandb.sdk.lib import hashutil

def test_special_characters_in_paths():
    manifest_data = {
        "version": 1,
        "storagePolicy": "wandb-storage-policy-v1",
        "storagePolicyConfig": {
            "storageLayout": "V2",
            "isTemporary": False
        },
        "contents": {
            "folder/file with spaces.txt": {
                "digest": "abc123==",
                "birthArtifactID": "abc123"
            },
            "special_chars/file#1@2$3.txt": {
                "digest": "def456==",
                "birthArtifactID": "def456"
            },
            "unicode/文件.txt": {
                "digest": "ghi789==",
                "birthArtifactID": "ghi789"
            },
            "special/file!@#$%^&*.txt": {
                "digest": "jkl012==",
                "birthArtifactID": "jkl012"
            }
        }
    }
    manifest = WandbArtifactManifest(manifest_data)
    base_url = "https://api.wandb.ai"

    test_cases = [
        {
            "uri": WeaveWBArtifactURI(
                entity_name="user space",
                project_name="project 1",
                name="artifact",
                version="v1",
                path="folder/file with spaces.txt"
            ),
            "expected_filename": "file%20with%20spaces.txt",
            "expected_entity": "user%20space",
            "expected_project": "project%201",
            "expected_artifact_name": "artifact",
            "expected_birth_artifact_id": "abc123"
        },
        {
            "uri": WeaveWBArtifactURI(
                entity_name="user@company",
                project_name="project$special",
                name="artifact",
                version="v1",
                path="special_chars/file#1@2$3.txt"
            ),
            "expected_filename": "file%231%402%243.txt",
            "expected_entity": "user%40company",
            "expected_project": "project%24special",
            "expected_artifact_name": "artifact",
            "expected_birth_artifact_id": "def456"
        },
        {
            "uri": WeaveWBArtifactURI(
                entity_name="user文件",
                project_name="project文件",
                name="artifact name",
                version="v1",
                path="unicode/文件.txt"
            ),
            "expected_filename": "%E6%96%87%E4%BB%B6.txt",
            "expected_entity": "user%E6%96%87%E4%BB%B6",
            "expected_project": "project%E6%96%87%E4%BB%B6",
            "expected_artifact_name": "artifact%20name",
            "expected_birth_artifact_id": "ghi789"
        },
        {
            "uri": WeaveWBArtifactURI(
                entity_name="user!@#",
                project_name="project^&*",
                name="artifact",
                version="v1",
                path="special/file!@#$%^&*.txt"
            ),
            "expected_filename": "file%21%40%23%24%25%5E%26%2A.txt",
            "expected_entity": "user%21%40%23",
            "expected_project": "project%5E%26%2A",
            "expected_artifact_name": "artifact",
            "expected_birth_artifact_id": "jkl012"
        }
    ]

    for tc in test_cases:
        _, download_url = _local_path_and_download_url(tc["uri"], manifest, base_url)
        
        expected_url = "{}/artifactsV2/default/{}/{}/{}/{}/{}/{}".format(
            base_url,
            tc["expected_entity"],
            tc["expected_project"],
            tc["expected_artifact_name"],
            tc["expected_birth_artifact_id"],
            hashutil.b64_to_hex_id(hashutil.B64MD5(manifest.get_entry_by_path(tc["uri"].path)["digest"])),
            tc["expected_filename"]
        )
        assert download_url == expected_url
        assert " " not in download_url
