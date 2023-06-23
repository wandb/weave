import datetime
import json
import typing
from wandb.apis.public import Run
from wandb.sdk.internal.file_pusher import FilePusher
from wandb.sdk.internal import file_stream
from wandb.sdk.internal.internal_api import Api as InternalApi
from wandb.sdk.lib import runid
from weave.wandb_client_api import wandb_public_api


class InMemoryLazyLiteRun:
    # ID
    _entity_name: str
    _project_name: str
    _run_name: str
    _step: int = 0

    # Optional
    _job_type: typing.Optional[str] = None

    # Property Cache
    _i_api: typing.Optional[InternalApi] = None
    _run: typing.Optional[Run] = None
    _stream: typing.Optional[file_stream.FileStreamApi] = None
    _pusher: typing.Optional[FilePusher] = None

    def __init__(
        self,
        entity_name: typing.Optional[str] = None,
        project_name: typing.Optional[str] = None,
        run_name: typing.Optional[str] = None,
        job_type: typing.Optional[str] = None,
    ):
        entity_name = entity_name or wandb_public_api().default_entity
        project_name = project_name or "uncategorized"

        assert entity_name is not None
        assert project_name is not None

        self._entity_name = entity_name
        self._project_name = project_name
        self._run_name = run_name or runid.generate_id()
        self._job_type = job_type

    def ensure_run(self) -> Run:
        return self.run

    @property
    def i_api(self) -> InternalApi:
        if self._i_api is None:
            self._i_api = InternalApi(
                {"project": self._project_name, "entity": self._entity_name}
            )
        return self._i_api

    @property
    def run(self) -> Run:
        if self._run is None:
            # Ensure project exists
            self.i_api.upsert_project(
                project=self._project_name, entity=self._entity_name
            )

            # Produce a run
            run_res, _, _ = self.i_api.upsert_run(
                name=self._run_name,
                job_type=self._job_type,
                project=self._project_name,
                entity=self._entity_name,
            )

            self._run = Run(
                wandb_public_api().client,
                run_res["project"]["entity"]["name"],
                run_res["project"]["name"],
                run_res["name"],
                {
                    "id": run_res["id"],
                    "config": "{}",
                    "systemMetrics": "{}",
                    "summaryMetrics": "{}",
                    "tags": [],
                    "description": None,
                    "notes": None,
                    "state": "running",
                },
            )

            self.i_api.set_current_run_id(self._run.id)
            # TODO: After gorilla is updated to support parallel runs
            # we can drop this completely
            self._step = self._run.lastHistoryStep + 1

        return self._run

    @property
    def stream(self) -> file_stream.FileStreamApi:
        if self._stream is None:
            # Setup the FileStream
            self._stream = file_stream.FileStreamApi(
                self.i_api, self.run.id, datetime.datetime.utcnow().timestamp()
            )
            self._stream.set_file_policy(
                "wandb-history.jsonl",
                file_stream.JsonlFilePolicy(start_chunk_id=self._step),
            )
            self._stream.start()

        return self._stream

    @property
    def pusher(self) -> FilePusher:
        if self._pusher is None:
            self._pusher = FilePusher(self.i_api, self.stream)

        return self._pusher

    def log(self, row_dict: dict) -> None:
        stream = self.stream
        row_dict = {
            **row_dict,
            # Required by gorilla
            # NOTE: This should be changed after gorilla is updated
            # to support parallel runs
            "_step": self._step,
            "_timestamp": datetime.datetime.utcnow().timestamp(),
        }
        self._step += 1
        stream.push("wandb-history.jsonl", json.dumps(row_dict))

    def finish(self) -> None:
        if self._stream is not None:
            # Finalize the run
            self.stream.finish(0)

        if self._pusher is not None:
            # Wait for the FilePusher and FileStream to finish
            self.pusher.finish()
            self.pusher.join()

        # Reset fields
        self._stream = None
        self._pusher = None
        self._run = None
        self._i_api = None
        self._step = 0

    def __del__(self) -> None:
        self.finish()
