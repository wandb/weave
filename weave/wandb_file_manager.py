# Safe class for managing W&B Artifact downloads. Can be used
# as the core of a fast artifact downloader, or a safe multiplexed
# file manager in the Weave server.

import datetime
import json
import typing
import base64
import urllib

from wandb.sdk.interface import artifacts
from wandb import util as wandb_util


from . import artifact_wandb
from . import errors
from . import engine_trace
from . import filesystem
from . import http
from . import wandb_api
from . import environment as weave_env
from . import cache


tracer = engine_trace.tracer()  # type: ignore


class WandbFileManagerAsync:
    def __init__(
        self,
        filesystem: filesystem.FilesystemAsync,
        http: http.HttpAsync,
        wandb_api: wandb_api.WandbApiAsync,
    ) -> None:
        self.fs = filesystem
        self.http = http
        self.wandb_api = wandb_api
        self._manifests: cache.LruTimeWindowCache[
            str, typing.Optional[artifacts.ArtifactManifest]
        ] = cache.LruTimeWindowCache(datetime.timedelta(minutes=5))

    def manifest_path(self, uri: artifact_wandb.WeaveWBArtifactURI) -> str:
        return f"{uri.entity_name}/{uri.project_name}/{uri.name}/manifest-{uri.version}.json"

    async def _manifest(
        self, art_uri: artifact_wandb.WeaveWBArtifactURI, manifest_path: str
    ) -> typing.Optional[artifacts.ArtifactManifest]:
        if art_uri.version is None:
            raise errors.WeaveInternalError(
                'Artifact URI has no version: "%s"' % art_uri
            )
        # Check if on disk
        try:
            async with self.fs.open_read(manifest_path) as f:
                return artifacts.ArtifactManifest.from_manifest_json(
                    None, json.loads(await f.read())
                )
        except FileNotFoundError:
            pass
        # Download
        manifest_url = await self.wandb_api.artifact_manifest_url(
            art_uri.entity_name,
            art_uri.project_name,
            art_uri.name + ":" + art_uri.version,
        )
        if manifest_url is None:
            return None
        await self.http.download_file(
            manifest_url,
            manifest_path,
        )
        async with self.fs.open_read(manifest_path) as f:
            return artifacts.ArtifactManifest.from_manifest_json(
                None, json.loads(await f.read())
            )

    async def manifest(
        self, art_uri: artifact_wandb.WeaveWBArtifactURI
    ) -> typing.Optional[artifacts.ArtifactManifest]:
        with tracer.trace("wandb_file_manager.manifest") as span:
            manifest_path = self.manifest_path(art_uri)
            manifest = self._manifests.get(manifest_path)
            if not isinstance(manifest, cache.LruTimeWindowCache.NotFound):
                return manifest
            manifest = await self._manifest(art_uri, manifest_path)
            self._manifests.set(manifest_path, manifest)
            return manifest

    def file_path(self, uri: artifact_wandb.WeaveWBArtifactURI, md5_hex: str) -> str:
        if uri.path is None:
            raise errors.WeaveInternalError(
                "Artifact URI has no path in call to file_path"
            )
        path_parts = uri.path.split(".", 1)
        if len(path_parts) == 2:
            extension = "." + path_parts[1]
        else:
            extension = ""
        return f"{uri.entity_name}/{uri.project_name}/{uri.name}/{md5_hex}{extension}"

    async def ensure_file(
        self, art_uri: artifact_wandb.WeaveWBArtifactURI
    ) -> typing.Optional[str]:
        path = art_uri.path
        if path is None:
            raise errors.WeaveInternalError(
                "Artifact URI has no path in call to ensure_file"
            )
        with tracer.trace("wandb_file_manager.ensure_file") as span:
            span.set_tag("uri", str(art_uri))
            manifest = await self.manifest(art_uri)
            if manifest is None:
                return None
            manifest_entry = manifest.get_entry_by_path(path)
            if manifest_entry is None:
                return None
            md5_hex = wandb_util.bytes_to_hex(base64.b64decode(manifest_entry.digest))
            file_path = self.file_path(art_uri, md5_hex)
            if await self.fs.exists(file_path):
                return file_path
            # TODO: storage_region
            storage_region = "default"
            base_url = weave_env.wandb_base_url()
            artifact_url = "{}/artifactsV2/{}/{}/{}/{}".format(
                base_url,
                storage_region,
                art_uri.entity_name,
                urllib.parse.quote(
                    manifest_entry.birth_artifact_id
                    if manifest_entry.birth_artifact_id is not None
                    else ""
                ),
                md5_hex,
            )
            wandb_api_context = wandb_api.get_wandb_api_context()
            headers = None
            cookies = None
            if wandb_api_context is not None:
                headers = wandb_api_context.headers
                cookies = wandb_api_context.cookies
            await self.http.download_file(
                artifact_url,
                file_path,
                headers=headers,
                cookies=cookies,
            )
            return file_path
