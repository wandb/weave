# Safe class for managing W&B Artifact downloads. Can be used
# as the core of a fast artifact downloader, or a safe multiplexed
# file manager in the Weave server.

import datetime
import json
import typing
import urllib
from aiohttp import BasicAuth

from wandb.sdk.lib import hashutil


from . import artifact_wandb
from . import errors
from . import engine_trace
from . import filesystem
from . import weave_http
from . import wandb_api
from . import environment as weave_env
from . import cache


from urllib import parse

tracer = engine_trace.tracer()  # type: ignore


def _file_path(uri: artifact_wandb.WeaveWBArtifactURI, md5_hex: str) -> str:
    if uri.path is None:
        raise errors.WeaveInternalError("Artifact URI has no path in call to file_path")
    path_parts = uri.path.split(".", 1)
    if len(path_parts) == 2:
        extension = "." + path_parts[1]
    else:
        extension = ""
    return f"wandb_file_manager/{uri.entity_name}/{uri.project_name}/{uri.name}/{md5_hex}{extension}"


def _local_path_and_download_url(
    art_uri: artifact_wandb.WeaveWBArtifactURI,
    manifest: artifact_wandb.WandbArtifactManifest,
) -> typing.Optional[typing.Tuple[str, str]]:
    path = art_uri.path
    if path is None:
        raise errors.WeaveInternalError(
            "Artifact URI has no path in call to _local_path_and_download_url"
        )
    file_name = path.split("/")[-1]
    manifest_entry = manifest.get_entry_by_path(path)
    if manifest_entry is None:
        return None
    md5_hex = hashutil.b64_to_hex_id(hashutil.B64MD5(manifest_entry["digest"]))
    base_url = weave_env.wandb_base_url()
    file_path = _file_path(art_uri, md5_hex)
    if manifest.storage_layout == artifact_wandb.WandbArtifactManifest.StorageLayout.V1:
        return file_path, "{}/artifacts/{}/{}/{}".format(
            base_url, art_uri.entity_name, md5_hex, urllib.parse.quote(file_name)
        )
    else:
        # TODO: storage_region
        storage_region = "default"
        return file_path, "{}/artifactsV2/{}/{}/{}/{}/{}".format(
            base_url,
            storage_region,
            art_uri.entity_name,
            urllib.parse.quote(manifest_entry.get("birthArtifactID", "")),  # type: ignore
            md5_hex,
            urllib.parse.quote(file_name),
        )


class WandbFileManagerAsync:
    def __init__(
        self,
        filesystem: filesystem.FilesystemAsync,
        http: weave_http.HttpAsync,
        wandb_api: wandb_api.WandbApiAsync,
    ) -> None:
        self.fs = filesystem
        self.http = http
        self.wandb_api = wandb_api
        self._manifests: cache.LruTimeWindowCache[
            str, typing.Optional[artifact_wandb.WandbArtifactManifest]
        ] = cache.LruTimeWindowCache(datetime.timedelta(minutes=5))

    def manifest_path(self, uri: artifact_wandb.WeaveWBArtifactURI) -> str:
        assert uri.version is not None
        return f"wandb_file_manager/{uri.entity_name}/{uri.project_name}/{uri.name}/manifest-{uri.version}.json"

    async def _manifest(
        self, art_uri: artifact_wandb.WeaveWBArtifactURI, manifest_path: str
    ) -> typing.Optional[artifact_wandb.WandbArtifactManifest]:
        if art_uri.version is None:
            raise errors.WeaveInternalError(
                'Artifact URI has no version: "%s"' % art_uri
            )
        # Check if on disk
        try:
            async with self.fs.open_read(manifest_path) as f:
                return artifact_wandb.WandbArtifactManifest(json.loads(await f.read()))
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
            return artifact_wandb.WandbArtifactManifest(json.loads(await f.read()))

    async def manifest(
        self, art_uri: artifact_wandb.WeaveWBArtifactURI
    ) -> typing.Optional[artifact_wandb.WandbArtifactManifest]:
        with tracer.trace("wandb_file_manager.manifest") as span:
            assert art_uri.version is not None
            manifest_path = self.manifest_path(art_uri)
            manifest = self._manifests.get(manifest_path)
            if not isinstance(manifest, cache.LruTimeWindowCache.NotFound):
                return manifest
            manifest = await self._manifest(art_uri, manifest_path)
            self._manifests.set(manifest_path, manifest)
            return manifest

    async def local_path_and_download_url(
        self, art_uri: artifact_wandb.WeaveWBArtifactURI
    ) -> typing.Optional[typing.Tuple[str, str]]:
        path = art_uri.path
        if path is None:
            raise errors.WeaveInternalError(
                "Artifact URI has no path in call to local_path_and_download_url"
            )
        manifest = await self.manifest(art_uri)
        if manifest is None:
            return None
        return _local_path_and_download_url(art_uri, manifest)

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
            res = await self.local_path_and_download_url(art_uri)
            if res is None:
                return None
            file_path, download_url = res
            if await self.fs.exists(file_path):
                return file_path
            wandb_api_context = wandb_api.get_wandb_api_context()
            headers = None
            cookies = None
            auth = None
            if wandb_api_context is not None:
                headers = wandb_api_context.headers
                cookies = wandb_api_context.cookies
                if wandb_api_context.api_key is not None:
                    auth = BasicAuth("api", wandb_api_context.api_key)
            await self.http.download_file(
                download_url,
                file_path,
                headers=headers,
                cookies=cookies,
                auth=auth,
            )
            return file_path

    async def ensure_file_downloaded(
        self,
        download_url: str,
    ) -> typing.Optional[str]:
        """Ensures a history parquet file from an http/https URI."""
        schema, netloc, path, _, _, _ = parse.urlparse(download_url)
        path = "/".join([netloc, path.lstrip("/")])
        if schema not in ("http", "https"):
            raise errors.WeaveInternalError(
                "ensure_file_downloaded only supports http/https URIs"
            )
        if path is None:
            raise errors.WeaveInternalError(
                "Artifact URI has no path in call to ensure_file"
            )
        with tracer.trace("wandb_file_manager.ensure_file_downloaded") as span:
            span.set_tag("download_url", str(download_url))
            file_path = f"wandb_file_manager/{path}"
            if await self.fs.exists(file_path):
                return file_path
            wandb_api_context = wandb_api.get_wandb_api_context()
            headers = None
            cookies = None
            auth = None
            if wandb_api_context is not None:
                headers = wandb_api_context.headers
                cookies = wandb_api_context.cookies
                if wandb_api_context.api_key is not None:
                    auth = BasicAuth("api", wandb_api_context.api_key)
            await self.http.download_file(
                download_url,
                file_path,
                headers=headers,
                cookies=cookies,
                auth=auth,
            )
            return file_path

    async def direct_url(
        self, art_uri: artifact_wandb.WeaveWBArtifactURI
    ) -> typing.Optional[str]:
        path = art_uri.path
        if path is None:
            raise errors.WeaveInternalError(
                "Artifact URI has no path in call to ensure_file"
            )
        with tracer.trace("wandb_file_manager.direct_url") as span:
            span.set_tag("uri", str(art_uri))
            res = await self.local_path_and_download_url(art_uri)
            if res is None:
                return None
            return res[1]


class WandbFileManager:
    def __init__(
        self,
        filesystem: filesystem.Filesystem,
        http: weave_http.Http,
        wandb_api: wandb_api.WandbApi,
    ) -> None:
        self.fs = filesystem
        self.http = http
        self.wandb_api = wandb_api
        self._manifests: cache.LruTimeWindowCache[
            str, typing.Optional[artifact_wandb.WandbArtifactManifest]
        ] = cache.LruTimeWindowCache(datetime.timedelta(minutes=5))

    def manifest_path(self, uri: artifact_wandb.WeaveWBArtifactURI) -> str:
        assert uri.version is not None
        return f"wandb_file_manager/{uri.entity_name}/{uri.project_name}/{uri.name}/manifest-{uri.version}.json"

    def _manifest(
        self, art_uri: artifact_wandb.WeaveWBArtifactURI, manifest_path: str
    ) -> typing.Optional[artifact_wandb.WandbArtifactManifest]:
        if art_uri.version is None:
            raise errors.WeaveInternalError(
                'Artifact URI has no version: "%s"' % art_uri
            )
        # Check if on disk
        try:
            with self.fs.open_read(manifest_path) as f:
                return artifact_wandb.WandbArtifactManifest(json.loads(f.read()))
        except FileNotFoundError:
            pass
        # Download
        manifest_url = self.wandb_api.artifact_manifest_url(
            art_uri.entity_name,
            art_uri.project_name,
            art_uri.name + ":" + art_uri.version,
        )
        if manifest_url is None:
            return None
        self.http.download_file(
            manifest_url,
            manifest_path,
        )
        with self.fs.open_read(manifest_path) as f:
            return artifact_wandb.WandbArtifactManifest(json.loads(f.read()))

    def manifest(
        self, art_uri: artifact_wandb.WeaveWBArtifactURI
    ) -> typing.Optional[artifact_wandb.WandbArtifactManifest]:
        with tracer.trace("wandb_file_manager.manifest") as span:
            assert art_uri.version is not None
            manifest_path = self.manifest_path(art_uri)
            manifest = self._manifests.get(manifest_path)
            if not isinstance(manifest, cache.LruTimeWindowCache.NotFound):
                return manifest
            manifest = self._manifest(art_uri, manifest_path)
            self._manifests.set(manifest_path, manifest)
            return manifest

    def local_path_and_download_url(
        self, art_uri: artifact_wandb.WeaveWBArtifactURI
    ) -> typing.Optional[typing.Tuple[str, str]]:
        path = art_uri.path
        if path is None:
            raise errors.WeaveInternalError(
                "Artifact URI has no path in call to local_path_and_download_url"
            )
        manifest = self.manifest(art_uri)
        if manifest is None:
            return None
        return _local_path_and_download_url(art_uri, manifest)

    def ensure_file_downloaded(
        self,
        download_url: str,
    ) -> typing.Optional[str]:
        """Ensures a history parquet file from an http/https URI."""
        schema, netloc, path, _, _, _ = parse.urlparse(download_url)
        path = "/".join([netloc, path.lstrip("/")])
        if schema not in ("http", "https"):
            raise errors.WeaveInternalError(
                "ensure_file_downloaded only supports http/https URIs"
            )
        if path is None:
            raise errors.WeaveInternalError(
                "Artifact URI has no path in call to ensure_file"
            )
        with tracer.trace("wandb_file_manager.ensure_file_downloaded") as span:
            span.set_tag("download_url", str(download_url))
            file_path = f"wandb_file_manager/{path}"
            if self.fs.exists(file_path):
                return file_path
            wandb_api_context = wandb_api.get_wandb_api_context()
            headers = None
            cookies = None
            if wandb_api_context is not None:
                headers = wandb_api_context.headers
                cookies = wandb_api_context.cookies
            self.http.download_file(
                download_url,
                file_path,
                headers=headers,
                cookies=cookies,
            )
            return file_path

    def ensure_file(
        self, art_uri: artifact_wandb.WeaveWBArtifactURI
    ) -> typing.Optional[str]:
        path = art_uri.path
        if path is None:
            raise errors.WeaveInternalError(
                "Artifact URI has no path in call to ensure_file"
            )
        with tracer.trace("wandb_file_manager.ensure_file") as span:
            span.set_tag("uri", str(art_uri))
            res = self.local_path_and_download_url(art_uri)
            if res is None:
                return None
            file_path, download_url = res
            if self.fs.exists(file_path):
                return file_path
            wandb_api_context = wandb_api.get_wandb_api_context()
            headers = None
            cookies = None
            if wandb_api_context is not None:
                headers = wandb_api_context.headers
                cookies = wandb_api_context.cookies
            self.http.download_file(
                download_url,
                file_path,
                headers=headers,
                cookies=cookies,
            )
            return file_path

    def direct_url(
        self, art_uri: artifact_wandb.WeaveWBArtifactURI
    ) -> typing.Optional[str]:
        path = art_uri.path
        if path is None:
            raise errors.WeaveInternalError(
                "Artifact URI has no path in call to ensure_file"
            )
        with tracer.trace("wandb_file_manager.direct_url") as span:
            span.set_tag("uri", str(art_uri))
            res = self.local_path_and_download_url(art_uri)
            if res is None:
                return None
            return res[1]
