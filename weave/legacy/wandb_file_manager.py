# Safe class for managing W&B Artifact downloads. Can be used
# as the core of a fast artifact downloader, or a safe multiplexed
# file manager in the Weave server.

import datetime
import json
import typing
import urllib
from urllib import parse

from aiohttp import BasicAuth
from requests.auth import HTTPBasicAuth
from wandb.sdk.lib import hashutil

from weave import engine_trace, errors, filesystem, weave_http
from weave import environment as weave_env
from weave.legacy import artifact_wandb, cache, wandb_api

tracer = engine_trace.tracer()  # type: ignore


def _file_path(
    uri: typing.Union[
        artifact_wandb.WeaveWBArtifactURI, artifact_wandb.WeaveWBArtifactByIDURI
    ],
    md5_hex: str,
) -> str:
    if uri.path is None:
        raise errors.WeaveInternalError("Artifact URI has no path in call to file_path")
    path_parts = uri.path.split(".", 1)
    if len(path_parts) == 2:
        extension = "." + path_parts[1]
    else:
        extension = ""
    if isinstance(uri, artifact_wandb.WeaveWBArtifactByIDURI):
        return f"wandb_file_manager/{uri.path_root}/{uri.artifact_id}/{uri.name}/{md5_hex}{extension}"
    return f"wandb_file_manager/{uri.entity_name}/{uri.project_name}/{uri.name}/{md5_hex}{extension}"


def _local_path_and_download_url(
    art_uri: typing.Union[
        artifact_wandb.WeaveWBArtifactURI, artifact_wandb.WeaveWBArtifactByIDURI
    ],
    manifest: artifact_wandb.WandbArtifactManifest,
    base_url: typing.Optional[str] = None,
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
    base_url = base_url or weave_env.wandb_base_url()
    file_path = _file_path(art_uri, md5_hex)
    # For artifactsV1 (legacy artifacts), the artifact's files cannot be fetched without the entity name, but
    # we substitute a '_' here anyway since artifact_uri.entity_name can be None accessed via an organization's
    # registry collection.
    if manifest.storage_layout == artifact_wandb.WandbArtifactManifest.StorageLayout.V1:
        return file_path, "{}/artifacts/{}/{}/{}".format(
            base_url, art_uri.entity_name or "_", md5_hex, urllib.parse.quote(file_name)
        )
    else:
        # TODO: storage_region
        storage_region = "default"
        # For artifactsV2 (which is all artifacts now), the file download handler ignores the entity
        # parameter while parsing the url, and fetches the files directly via the artifact id
        # Refer to: https://github.com/wandb/core/blob/7cfee1cd07ddc49fe7ba70ce3d213d2a11bd4456/services/gorilla/api/handler/artifacts.go#L179
        return file_path, "{}/artifactsV2/{}/{}/{}/{}/{}".format(
            base_url,
            storage_region,
            art_uri.entity_name or "_",
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

    def manifest_path(
        self,
        uri: typing.Union[
            artifact_wandb.WeaveWBArtifactURI, artifact_wandb.WeaveWBArtifactByIDURI
        ],
    ) -> str:
        assert uri.version is not None
        if isinstance(uri, artifact_wandb.WeaveWBArtifactURI):
            return f"wandb_file_manager/{uri.entity_name}/{uri.project_name}/{uri.name}/manifest-{uri.version}.json"
        return f"wandb_file_manager/{uri.path_root}/{uri.artifact_id}/{uri.name}/manifest-{uri.version}.json"

    async def _manifest(
        self,
        art_uri: typing.Union[
            artifact_wandb.WeaveWBArtifactURI, artifact_wandb.WeaveWBArtifactByIDURI
        ],
        manifest_path: str,
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
        manifest_url = None
        if isinstance(art_uri, artifact_wandb.WeaveWBArtifactByIDURI):
            artifact_id = art_uri.artifact_id
            manifest_url = await self.wandb_api.artifact_manifest_url_from_id(
                art_id=artifact_id,
            )
        else:
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
        self,
        art_uri: typing.Union[
            artifact_wandb.WeaveWBArtifactURI, artifact_wandb.WeaveWBArtifactByIDURI
        ],
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
        self,
        art_uri: typing.Union[
            artifact_wandb.WeaveWBArtifactURI, artifact_wandb.WeaveWBArtifactByIDURI
        ],
        base_url: typing.Optional[str] = None,
    ) -> typing.Optional[typing.Tuple[str, str]]:
        path = art_uri.path
        if path is None:
            raise errors.WeaveInternalError(
                "Artifact URI has no path in call to local_path_and_download_url"
            )
        manifest = await self.manifest(art_uri)
        if manifest is None:
            return None
        return _local_path_and_download_url(art_uri, manifest, base_url)

    async def ensure_file(
        self,
        art_uri: typing.Union[
            artifact_wandb.WeaveWBArtifactURI, artifact_wandb.WeaveWBArtifactByIDURI
        ],
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
        self,
        art_uri: typing.Union[
            artifact_wandb.WeaveWBArtifactURI, artifact_wandb.WeaveWBArtifactByIDURI
        ],
    ) -> typing.Optional[str]:
        path = art_uri.path
        if path is None:
            raise errors.WeaveInternalError(
                "Artifact URI has no path in call to ensure_file"
            )
        with tracer.trace("wandb_file_manager.direct_url") as span:
            span.set_tag("uri", str(art_uri))
            res = await self.local_path_and_download_url(
                art_uri, base_url=weave_env.wandb_frontend_base_url()
            )
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

    def manifest_path(
        self,
        uri: typing.Union[
            artifact_wandb.WeaveWBArtifactURI, artifact_wandb.WeaveWBArtifactByIDURI
        ],
    ) -> str:
        assert uri.version is not None
        if isinstance(uri, artifact_wandb.WeaveWBArtifactByIDURI):
            return f"wandb_file_manager/{uri.path_root}/{uri.artifact_id}/{uri.name}/manifest-{uri.version}.json"
        return f"wandb_file_manager/{uri.entity_name}/{uri.project_name}/{uri.name}/manifest-{uri.version}.json"

    def _manifest(
        self,
        art_uri: typing.Union[
            artifact_wandb.WeaveWBArtifactURI, artifact_wandb.WeaveWBArtifactByIDURI
        ],
        manifest_path: str,
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
        manifest_url = None
        if isinstance(art_uri, artifact_wandb.WeaveWBArtifactByIDURI):
            artifact_id = art_uri.artifact_id
            manifest_url = self.wandb_api.artifact_manifest_url_from_id(
                art_id=artifact_id,
            )
        else:
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
        self,
        art_uri: typing.Union[
            artifact_wandb.WeaveWBArtifactURI, artifact_wandb.WeaveWBArtifactByIDURI
        ],
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
        self,
        art_uri: typing.Union[
            artifact_wandb.WeaveWBArtifactURI, artifact_wandb.WeaveWBArtifactByIDURI
        ],
        base_url: typing.Optional[str] = None,
    ) -> typing.Optional[typing.Tuple[str, str]]:
        path = art_uri.path
        if path is None:
            raise errors.WeaveInternalError(
                "Artifact URI has no path in call to local_path_and_download_url"
            )
        manifest = self.manifest(art_uri)
        if manifest is None:
            return None
        return _local_path_and_download_url(art_uri, manifest, base_url)

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
            auth = None
            if wandb_api_context is not None:
                headers = wandb_api_context.headers
                cookies = wandb_api_context.cookies
                if wandb_api_context.api_key is not None:
                    auth = HTTPBasicAuth("api", wandb_api_context.api_key)
            self.http.download_file(
                download_url, file_path, headers=headers, cookies=cookies, auth=auth
            )
            return file_path

    def ensure_file(
        self,
        art_uri: typing.Union[
            artifact_wandb.WeaveWBArtifactURI, artifact_wandb.WeaveWBArtifactByIDURI
        ],
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
            auth = None
            if wandb_api_context is not None:
                headers = wandb_api_context.headers
                cookies = wandb_api_context.cookies
                if wandb_api_context.api_key is not None:
                    auth = HTTPBasicAuth("api", wandb_api_context.api_key)
            self.http.download_file(
                download_url, file_path, headers=headers, cookies=cookies, auth=auth
            )
            return file_path

    def direct_url(
        self,
        art_uri: typing.Union[
            artifact_wandb.WeaveWBArtifactURI, artifact_wandb.WeaveWBArtifactByIDURI
        ],
    ) -> typing.Optional[str]:
        path = art_uri.path
        if path is None:
            raise errors.WeaveInternalError(
                "Artifact URI has no path in call to ensure_file"
            )
        with tracer.trace("wandb_file_manager.direct_url") as span:
            span.set_tag("uri", str(art_uri))
            res = self.local_path_and_download_url(
                art_uri, base_url=weave_env.wandb_frontend_base_url()
            )
            if res is None:
                return None
            return res[1]
