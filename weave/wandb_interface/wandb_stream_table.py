import atexit
import contextlib
import datetime
import json
import logging
import os
import queue
import random
import shutil
import threading
import typing
import uuid

from wandb.sdk.lib.paths import LogicalPath
from wandb.sdk.lib.printer import get_printer
from wandb.sdk.lib.ipython import _get_python_type

from .wandb_lite_run import InMemoryLazyLiteRun

from .. import wandb_api
from .. import runfiles_wandb
from .. import storage
from .. import weave_types
from .. import artifact_base
from .. import environment
from .. import file_util
from .. import graph
from .. import errors
from ..core_types.stream_table_type import StreamTableType
from ..ops_domain import stream_table_ops
from ..ops_primitives import weave_api

if typing.TYPE_CHECKING:
    from wandb.sdk.internal.file_pusher import FilePusher


# Shawn recommended we only encode leafs, but in my testing, nested structures
# are not handled as well in in gorilla and we can do better using just weave.
# Uncomment the below to use gorilla for nested structures.
TRUST_GORILLA_FOR_NESTED_STRUCTURES = True

# Weave types are parametrized, but gorilla expects just simple strings. We could
# send the top-level string over the wire, but this fails to encode type specifics
# and therefore loses information. With this flag, we instead stringify the JSON type
# and send that over the wire. This is a bit of a hack, but it works.
ENCODE_ENTIRE_TYPE = True
TYPE_ENCODE_PREFIX = "_wt_::"

ROW_TYPE = typing.Union[typing.Mapping, list[typing.Mapping]]


class WandbLiveRunFiles(runfiles_wandb.WandbRunFiles):
    _file_pusher: typing.Optional["FilePusher"] = None
    _temp_dir: typing.Optional[str] = None

    def set_file_pusher(self, pusher: "FilePusher") -> None:
        # It is the responsibility of the caller to ensure this file pusher is
        # correctly associated with the corresponding run.
        self._file_pusher = pusher

    def temp_dir(self) -> str:
        if self._temp_dir is None:
            rand_part = "".join(random.choice("0123456789ABCDEF") for _ in range(16))
            self._temp_dir = os.path.join(
                runfiles_wandb.wandb_run_dir(), "upload_cache", f"tmp_{rand_part}"
            )
            os.makedirs(self._temp_dir, exist_ok=True)
        return self._temp_dir

    def cleanup(self) -> None:
        if self._temp_dir is not None:
            shutil.rmtree(self._temp_dir)
            self._temp_dir = None

    def __del__(self) -> None:
        self.cleanup()

    @contextlib.contextmanager
    def new_file(
        self, path: str, binary: bool = False
    ) -> typing.Generator[typing.IO, None, None]:
        if self._file_pusher is None:
            raise ValueError(
                "WandbLiveRunFiles must be associated with a file pusher to use new_file"
            )

        dir_path = self.temp_dir()
        file_path = os.path.join(dir_path, path)
        with file_util.safe_open(file_path, "wb" if binary else "w") as file:
            yield file
            self._file_pusher.file_changed(LogicalPath(path), file_path)


class _StreamTableSync:
    _lite_run: InMemoryLazyLiteRun
    _table_name: str
    _project_name: str
    _entity_name: str

    _artifact: WandbLiveRunFiles

    _weave_stream_table: StreamTableType
    _weave_stream_table_ref: artifact_base.ArtifactRef

    _client_id: str

    def __init__(
        self,
        table_name: str,
        *,
        project_name: typing.Optional[str] = None,
        entity_name: typing.Optional[str] = None,
        _disable_async_file_stream: bool = False,
    ):
        self._client_id = str(uuid.uuid1())
        splits = table_name.split("/")
        if len(splits) == 1:
            pass
        elif len(splits) == 2:
            if project_name is not None:
                raise ValueError(
                    f"Cannot specify project_name and table_name with '/' in it: {table_name}"
                )
            project_name = splits[0]
            table_name = splits[1]
        elif len(splits) == 3:
            if project_name is not None or entity_name is not None:
                raise ValueError(
                    f"Cannot specify project_name or entity_name and table_name with 2 '/'s in it: {table_name}"
                )
            entity_name = splits[0]
            project_name = splits[1]
            table_name = splits[2]

        if entity_name is None or entity_name == "":
            # Use user's default entity
            api = wandb_api.get_wandb_api_sync()
            entity_name = api.default_entity_name()
            # get default entity
            if entity_name is None or entity_name == "":
                raise ValueError(
                    "Entity not specified and no default entity found. Please specify entity_name or set default entity with `wandb login --entity <entity_name>`"
                )

        if project_name is None or project_name == "":
            raise ValueError("Must specify project_name")
        elif table_name is None or table_name == "":
            raise ValueError("Must specify table_name")

        self._lite_run = InMemoryLazyLiteRun(
            entity_name,
            project_name,
            table_name,
            group="weave_stream_tables",
            _hide_in_wb=True,
            _use_async_file_stream=not _disable_async_file_stream,
        )
        self._table_name = self._lite_run._run_name
        self._project_name = self._lite_run._project_name
        self._entity_name = self._lite_run._entity_name
        self._ensure_remote_initialized()
        atexit.register(self._at_exit)

    def _ensure_remote_initialized(self) -> StreamTableType:
        self._lite_run.ensure_run()
        print_url = False
        if not hasattr(self, "_weave_stream_table"):
            print_url = True
            self._weave_stream_table = StreamTableType(
                table_name=self._table_name,
                project_name=self._project_name,
                entity_name=self._entity_name,
            )
            self._weave_stream_table_ref = storage._direct_publish(
                self._weave_stream_table,
                name=self._table_name,
                wb_project_name=self._project_name,
                wb_entity_name=self._entity_name,
                _lite_run=self._lite_run,
            )
        if not hasattr(self, "_artifact"):
            uri = runfiles_wandb.WeaveWBRunFilesURI.from_run_identifiers(
                self._entity_name,
                self._project_name,
                self._table_name,
            )
            self._artifact = WandbLiveRunFiles(name=uri.name, uri=uri)
            self._artifact.set_file_pusher(self._lite_run.pusher)
        if print_url:
            base_url = environment.weave_server_url()
            url = f"{base_url}/browse/wandb/{self._entity_name}/{self._project_name}/table/{self._table_name}"
            printer = get_printer(_get_python_type() != "python")
            printer.display(f'{printer.emoji("star")} View data at {printer.link(url)}')
        return self._weave_stream_table

    def log(self, row_or_rows: ROW_TYPE) -> None:
        if isinstance(row_or_rows, dict):
            row_or_rows = [row_or_rows]

        for row in row_or_rows:
            self._log_row(row)

    def rows(self) -> graph.Node:
        if self._weave_stream_table_ref is None:
            raise errors.WeaveInternalError("ref is None after ensure")
        return stream_table_ops.rows(
            weave_api.get(str(self._weave_stream_table_ref.uri))
        )

    def _ipython_display_(self) -> graph.Node:
        from .. import show

        return show(self.rows())

    def _log_row(self, row: typing.Mapping) -> None:
        row_copy = {**row}
        row_copy["_client_id"] = self._client_id
        if "timestamp" not in row_copy:
            row_copy["timestamp"] = datetime.datetime.now()
        payload = row_to_weave(row_copy, self._artifact)
        self._lite_run.log(payload)

    def finish(self) -> None:
        if self._lite_run:
            self._lite_run.finish()
        if self._artifact:
            self._artifact.cleanup()

    def __del__(self) -> None:
        self.finish()

    def _at_exit(self) -> None:
        self.finish()


class StreamTable(_StreamTableSync):
    MAX_UNSAVED_SECONDS = 2

    def __init__(
        self,
        table_name: str,
        *,
        project_name: typing.Optional[str] = None,
        entity_name: typing.Optional[str] = None,
        _disable_async_file_stream: bool = False,
    ):
        super().__init__(
            table_name=table_name,
            project_name=project_name,
            entity_name=entity_name,
            _disable_async_file_stream=_disable_async_file_stream,
        )

        self.queue: queue.Queue = queue.Queue()
        atexit.register(self._at_exit)
        self._lock = threading.Lock()
        self._join_event = threading.Event()
        self._thread = threading.Thread(target=self._thread_body)
        self._thread.daemon = True
        self._thread.start()

    def log(self, row_or_rows: ROW_TYPE) -> None:
        # weave_types.TypeRegistry.type_of(row_or_rows)
        self.queue.put(row_or_rows)

    def _flush(self) -> None:
        with self._lock:
            for log_payload in self._iterate_queue():
                super().log(log_payload)

    def _iterate_queue(
        self,
    ) -> typing.Generator[ROW_TYPE, None, None]:
        while True:
            try:
                record = self.queue.get_nowait()
            except queue.Empty:
                break
            else:
                yield record
                self.queue.task_done()

    def _thread_body(self) -> None:
        join_requested = False
        while not join_requested:
            join_requested = self._join_event.wait(self.MAX_UNSAVED_SECONDS)
            self._flush()

    # Override methods of _StreamTableSync
    def finish(self) -> None:
        if hasattr(self, "_thread"):
            self._join_event.set()
            self._thread.join()
            with self._lock:
                super().finish()


def maybe_history_type_to_weave_type(tc_type: str) -> typing.Optional[weave_types.Type]:
    if tc_type.startswith(TYPE_ENCODE_PREFIX):
        w_type = json.loads(tc_type[len(TYPE_ENCODE_PREFIX) :])
        try:
            return weave_types.TypeRegistry.type_from_dict(w_type)
        except Exception as e:
            logging.warning(
                f"StreamTable Type Error: Found type for {tc_type}, but blind construction failed: {e}",
            )
    else:
        possible_type = weave_types.type_name_to_type(tc_type)
        if possible_type is not None:
            try:
                return possible_type()
            except Exception as e:
                logging.warning(
                    f"StreamTable Type Error: Found type for {tc_type}, but blind construction failed: {e}",
                )
    return None


def is_weave_encoded_history_cell(cell: dict) -> bool:
    return "_val" in cell and (
        "_weave_type" in cell
        or (cell.get("_type") != None and cell["_type"].startswith(TYPE_ENCODE_PREFIX))
    )


def from_weave_encoded_history_cell(cell: dict) -> typing.Any:
    if not is_weave_encoded_history_cell(cell):
        raise ValueError(f"Expected weave encoded history cell, got {cell}")
    if "_weave_type" in cell:
        weave_type = cell["_weave_type"]
    elif cell["_type"].startswith(TYPE_ENCODE_PREFIX):
        weave_type = json.loads(cell["_type"][len(TYPE_ENCODE_PREFIX) :])
    else:
        raise ValueError(f"Expected weave encoded history cell, got {cell}")
    weave_json = {
        "_type": weave_type,
        "_val": cell["_val"],
    }
    return storage.from_python(weave_json)


def row_to_weave(
    row: typing.Dict[str, typing.Any], artifact: WandbLiveRunFiles
) -> typing.Dict[str, typing.Any]:
    return {key: obj_to_weave(value, artifact) for key, value in row.items()}


def obj_to_weave(obj: typing.Any, artifact: WandbLiveRunFiles) -> typing.Any:
    def recurse(obj: typing.Any) -> typing.Any:
        return obj_to_weave(obj, artifact)

    # all primitives
    if isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    else:
        if TRUST_GORILLA_FOR_NESTED_STRUCTURES:
            if isinstance(obj, dict):
                return {key: recurse(value) for key, value in obj.items()}
            elif isinstance(obj, list):
                return [recurse(value) for value in obj]
            elif isinstance(obj, tuple):
                return [recurse(value) for value in obj]
            elif isinstance(obj, set):
                return [recurse(value) for value in obj]
            elif isinstance(obj, frozenset):
                return [recurse(value) for value in obj]
            else:
                return leaf_to_weave(obj, artifact)
        else:
            return leaf_to_weave(obj, artifact)


def w_type_to_type_name(w_type: typing.Union[str, dict]) -> str:
    if isinstance(w_type, str):
        return w_type
    if ENCODE_ENTIRE_TYPE:
        return TYPE_ENCODE_PREFIX + json.dumps(w_type)
    else:
        return w_type["type"]


def leaf_to_weave(leaf: typing.Any, artifact: WandbLiveRunFiles) -> typing.Any:
    def ref_persister_artifact(
        type: weave_types.Type, refs: typing.Iterable[artifact_base.ArtifactRef]
    ) -> artifact_base.Artifact:
        # Save all the reffed objects into the new artifact.
        for mem_ref in refs:
            if mem_ref.path is not None and mem_ref._type is not None:
                # Hack: add a random salt to the end (i really want content addressing here)
                # but this is a quick fix to avoid collisions
                path = mem_ref.path + "-" + str(uuid.uuid4())
                artifact.set(path, mem_ref._type, mem_ref._obj)
        return artifact

    res = storage.to_python(leaf, None, ref_persister_artifact)

    w_type = res["_type"]
    type_name = w_type_to_type_name(w_type)

    if ENCODE_ENTIRE_TYPE:
        return {"_type": type_name, "_val": res["_val"]}
    else:
        return {
            "_type": type_name,
            "_weave_type": w_type,
            "_val": res["_val"],
        }
