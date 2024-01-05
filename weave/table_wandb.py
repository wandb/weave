import dataclasses
import uuid
import functools
from urllib import parse
from typing import Any, Optional
from . import graph_client_context
from . import graph_client_wandb_art_st
from . import uris
from . import errors
from . import ref_base
from . import weave_internal
from . import context_state
from . import ops_primitives
from . import weave_types as types
from .monitoring import StreamTable

quote_slashes = functools.partial(parse.quote, safe="")


@dataclasses.dataclass
class WandbTableURI(uris.WeaveURI):
    SCHEME = "wandb-table"
    entity_name: str
    project_name: str
    netloc: Optional[str] = None
    row_id: Optional[str] = None
    row_version: Optional[str] = None
    extra: Optional[list[str]] = None

    @classmethod
    def from_parsed_uri(
        cls,
        uri: str,
        schema: str,
        netloc: str,
        path: str,
        params: str,
        query: dict[str, list[str]],
        fragment: str,
    ):
        parts = path.strip("/").split("/")
        parts = [parse.unquote(part) for part in parts]
        if len(parts) < 3:
            raise errors.WeaveInvalidURIError(f"Invalid WB Artifact URI: {uri}")
        entity_name = parts[0]
        project_name = parts[1]
        table_name = parts[2]
        row_id = None
        if len(parts) > 3:
            row_id = parts[3]
        row_version = None
        if len(parts) > 4:
            row_version = parts[4]

        extra: Optional[list[str]] = None
        if fragment:
            extra = fragment.split("/")
        return cls(
            table_name,
            None,
            entity_name,
            project_name,
            netloc,
            row_id,
            row_version,
            extra,
        )

    def __str__(self) -> str:
        netloc = self.netloc or ""
        uri = (
            f"{self.SCHEME}://"
            f"{quote_slashes(netloc)}/"
            f"{quote_slashes(self.entity_name)}/"
            f"{quote_slashes(self.project_name)}/"
            f"{quote_slashes(self.name)}"
        )
        if self.row_id:
            uri += f"/{quote_slashes(self.row_id)}"
        if self.row_version:
            uri += f"/{quote_slashes(self.row_version)}"
        if self.extra:
            uri += f"#{'/'.join(self.extra)}"
        return uri

    def to_ref(self) -> "WandbTableRef":
        return WandbTableRef.from_uri(self)


class WandbTableRef(ref_base.Ref):
    def __init__(
        self,
        entity_name: str,
        project_name: str,
        table_name: str,
        row_id: Optional[str],
        row_version: Optional[str],
        obj: Optional[Any] = None,
        type: Optional["types.Type"] = None,
        extra: Optional[list[str]] = None,
    ):
        self._entity_name = entity_name
        self._project_name = project_name
        self._table_name = table_name
        self._row_id = row_id
        self._row_version = row_version
        super().__init__(obj=obj, type=type)

    @classmethod
    def from_uri(cls, uri: uris.WeaveURI) -> "WandbTableRef":
        if not isinstance(uri, WandbTableURI):
            raise ValueError("Expected WandbTableURI")
        return cls(
            uri.entity_name,
            uri.project_name,
            uri.name,
            uri.row_id,
            uri.row_version,
            extra=uri.extra,
        )

    @property
    def is_saved(self) -> bool:
        return True

    @property
    def type(self) -> "types.Type":
        if self._type is None:
            # TODO: expensive
            self._type = types.TypeRegistry.type_of(self.obj)
        return self._type

    @property
    def initial_uri(self) -> str:
        return self.uri

    @property
    def uri(self) -> str:
        return str(
            WandbTableURI(
                self._table_name,
                None,
                self._entity_name,
                self._project_name,
                None,  # netloc ?
                row_id=self._row_id,
                row_version=self._row_version,
                extra=self.extra,
            )
        )

    def _get(self) -> Any:
        t = WandbTable(
            self._table_name,
            entity_name=self._entity_name,
            project_name=self._project_name,
        )
        if self._row_id is None:
            return t
        return t.get(self._row_id, version=self._row_version)

    def __repr__(self) -> str:
        return f"<{self.__class__}({id(self)}) entity_name={self._entity_name} project_name={self._project_name} table_name={self._table_name} row_id={self._row_id} row_version={self._row_version} obj={self._obj} type={self._type}>"


# TODO: we'll make a table protocol, but for now this is the only one
class WandbTable:
    def __init__(
        self,
        name: str,
        entity_name: Optional[str] = None,
        project_name: Optional[str] = None,
        uri: Optional[str] = None,
    ) -> None:
        if entity_name is None or project_name is None:
            client = graph_client_context.require_graph_client()
            if not isinstance(
                client, graph_client_wandb_art_st.GraphClientWandbArtStreamTable
            ):
                raise ValueError(
                    "Provide entity_name and project_name, or call weave.init()"
                )
            if entity_name is None:
                entity_name = client.entity_name
            if project_name is None:
                project_name = client.project_name

        # TODO: should be able to init this without client

        self._streamtable = StreamTable(
            name, project_name=project_name, entity_name=entity_name
        )

    def add(self, obj: Any, id: Optional[str] = None) -> WandbTableRef:
        if id is None:
            id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        self._streamtable.log({"id": id, "version_id": version_id, "obj": obj})
        return WandbTableRef(
            entity_name=self._streamtable._entity_name,
            project_name=self._streamtable._project_name,
            table_name=self._streamtable._table_name,
            row_id=id,
            row_version=version_id,
            obj=obj,
        )

    def get(self, id_: str, version: Optional[str] = None) -> Any:
        with context_state.lazy_execution():
            if version is None:
                node = self._streamtable.rows().filter(lambda row: row["id"] == id_)[
                    -1
                ]["obj"]
            else:
                node = self._streamtable.rows().filter(
                    lambda row: ops_primitives.Boolean.bool_and(
                        row["id"] == id_, row["version_id"] == version
                    )
                )[0]["obj"]
            return weave_internal.use(node)
