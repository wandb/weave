"""Evaluation domain methods for the ClickHouse trace server."""

import datetime
from collections.abc import Iterator

from weave.shared import refs_internal as ri
from weave.trace_server import (
    constants,
    object_creation_utils,
)
from weave.trace_server import eval_results_helpers as eval_helpers
from weave.trace_server import trace_server_common as tsc
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import NotFoundError
from weave.trace_server.ids import generate_id
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.interface.feedback_types import RUNNABLE_FEEDBACK_TYPE_PREFIX
from weave.trace_server.methods.evaluation_status import evaluation_status
from weave.trace_server.trace_server_common import determine_call_status
from weave.trace_server.workers.evaluate_model_worker.evaluate_model_worker import (
    EvaluateModelArgs,
)

OBJ_READ_RETRY_ATTEMPTS = 3


class EvalDomainMixin:
    def scorer_create(self, req: tsi.ScorerCreateReq) -> tsi.ScorerCreateRes:
        """Create a scorer object by first creating its score op, then creating the scorer object.

        The scorer object references the op that implements the scoring logic.
        """
        # Create a safe ID for the scorer
        scorer_id = object_creation_utils.make_object_id(req.name, "Scorer")

        # Create the score op
        score_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=f"{scorer_id}_score",
            source_code=req.op_source_code,
        )
        score_op_res = self.op_create(score_op_req)
        score_op_ref = score_op_res.digest

        # Create the default summarize op
        summarize_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=f"{scorer_id}_summarize",
            source_code=object_creation_utils.PLACEHOLDER_SCORER_SUMMARIZE_OP_SOURCE,
        )
        summarize_op_res = self.op_create(summarize_op_req)
        summarize_op_ref = summarize_op_res.digest

        # Create the scorer object
        scorer_val = object_creation_utils.build_scorer_val(
            name=req.name,
            description=req.description,
            score_op_ref=score_op_ref,
            summarize_op_ref=summarize_op_ref,
        )
        obj_req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=req.project_id,
                object_id=scorer_id,
                val=scorer_val,
                wb_user_id=None,
            )
        )
        obj_result = self.obj_create(obj_req)

        # Query the object back to get its version index (this may not be
        # immediately available, so we retry a few times)
        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=scorer_id,
            digest=obj_result.digest,
        )
        obj_read_res = self._obj_read_with_retry(
            obj_read_req, max_attempts=OBJ_READ_RETRY_ATTEMPTS
        )

        # Get the ref and return the create result
        scorer_ref = ri.InternalObjectRef(
            project_id=req.project_id,
            name=scorer_id,
            version=obj_result.digest,
        ).uri
        return tsi.ScorerCreateRes(
            digest=obj_result.digest,
            object_id=scorer_id,
            version_index=obj_read_res.obj.version_index,
            scorer=scorer_ref,
        )

    def scorer_read(self, req: tsi.ScorerReadReq) -> tsi.ScorerReadRes:
        """Get a scorer object by delegating to obj_read with retry logic."""
        obj_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
        )
        result = self._obj_read_with_retry(obj_req)
        return tsc.scorer_read_res_from_obj(result.obj)

    def scorer_list(self, req: tsi.ScorerListReq) -> Iterator[tsi.ScorerReadRes]:
        """List scorer objects by delegating to objs_query with Scorer filtering."""
        scorer_filter = tsi.ObjectVersionFilter(
            base_object_classes=["Scorer"], is_op=False
        )
        obj_query_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=scorer_filter,
            limit=req.limit,
            offset=req.offset,
        )
        obj_res = self.objs_query(obj_query_req)

        for obj in obj_res.objs:
            yield tsc.scorer_read_res_from_obj(obj)

    def scorer_delete(self, req: tsi.ScorerDeleteReq) -> tsi.ScorerDeleteRes:
        """Delete scorer objects by delegating to obj_delete."""
        obj_delete_req = tsi.ObjDeleteReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )
        result = self.obj_delete(obj_delete_req)
        return tsi.ScorerDeleteRes(num_deleted=result.num_deleted)

    def evaluation_create(
        self, req: tsi.EvaluationCreateReq
    ) -> tsi.EvaluationCreateRes:
        """Create an evaluation object.

        Creates placeholder ops for evaluate, predict_and_score, and summarize methods.
        """
        # Create a safe ID for the evaluation
        evaluation_id = object_creation_utils.make_object_id(req.name, "Evaluation")

        # Create placeholder evaluate op
        evaluate_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=f"{evaluation_id}.evaluate",
            source_code=object_creation_utils.PLACEHOLDER_EVALUATE_OP_SOURCE,
        )
        evaluate_op_res = self.op_create(evaluate_op_req)
        evaluate_ref = evaluate_op_res.digest

        # Create placeholder predict_and_score op
        predict_and_score_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=f"{evaluation_id}.predict_and_score",
            source_code=object_creation_utils.PLACEHOLDER_PREDICT_AND_SCORE_OP_SOURCE,
        )
        predict_and_score_op_res = self.op_create(predict_and_score_op_req)
        predict_and_score_ref = predict_and_score_op_res.digest

        # Create placeholder summarize op
        summarize_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=f"{evaluation_id}.summarize",
            source_code=object_creation_utils.PLACEHOLDER_EVALUATION_SUMMARIZE_OP_SOURCE,
        )
        summarize_op_res = self.op_create(summarize_op_req)
        summarize_ref = summarize_op_res.digest

        # Create the evaluation object
        evaluation_val = object_creation_utils.build_evaluation_val(
            name=req.name,
            dataset_ref=req.dataset,
            trials=req.trials,
            description=req.description,
            scorer_refs=req.scorers,
            evaluation_name=req.evaluation_name,
            metadata=None,
            preprocess_model_input=None,
            eval_attributes=req.eval_attributes,
            evaluate_ref=evaluate_ref,
            predict_and_score_ref=predict_and_score_ref,
            summarize_ref=summarize_ref,
        )
        obj_req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=req.project_id,
                object_id=evaluation_id,
                val=evaluation_val,
                wb_user_id=None,
            )
        )
        obj_result = self.obj_create(obj_req)

        # Query the object back to get its version index (this may not be
        # immediately available, so we retry a few times)
        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=evaluation_id,
            digest=obj_result.digest,
        )
        obj_read_res = self._obj_read_with_retry(
            obj_read_req, max_attempts=OBJ_READ_RETRY_ATTEMPTS
        )

        # Get the ref and return the create result
        evaluation_ref = ri.InternalObjectRef(
            project_id=req.project_id,
            name=evaluation_id,
            version=obj_result.digest,
        ).uri
        return tsi.EvaluationCreateRes(
            digest=obj_result.digest,
            object_id=evaluation_id,
            version_index=obj_read_res.obj.version_index,
            evaluation_ref=evaluation_ref,
        )

    def evaluation_read(self, req: tsi.EvaluationReadReq) -> tsi.EvaluationReadRes:
        """Get an evaluation object by delegating to obj_read with retry logic."""
        obj_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
        )
        result = self._obj_read_with_retry(obj_req)
        val = result.obj.val

        # Extract name and description from val data
        name = val.get("name")
        description = val.get("description")

        # Create the response with all required fields
        return tsi.EvaluationReadRes(
            object_id=result.obj.object_id,
            digest=result.obj.digest,
            version_index=result.obj.version_index,
            created_at=result.obj.created_at,
            name=name,
            description=description,
            dataset=val.get("dataset", ""),
            scorers=val.get("scorers", []),
            trials=val.get("trials", 1),
            evaluation_name=val.get("evaluation_name"),
            evaluate_op=val.get("evaluate", ""),
            predict_and_score_op=val.get("predict_and_score", ""),
            summarize_op=val.get("summarize", ""),
        )

    def evaluation_list(
        self, req: tsi.EvaluationListReq
    ) -> Iterator[tsi.EvaluationReadRes]:
        """List evaluation objects by delegating to objs_query with Evaluation filtering."""
        # Query the objects
        obj_query_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=tsi.ObjectVersionFilter(
                base_object_classes=["Evaluation"], is_op=False
            ),
            limit=req.limit,
            offset=req.offset,
        )
        result = self.objs_query(obj_query_req)

        # Yield back a descriptive metadata object for each evaluation
        for obj in result.objs:
            val = obj.val if hasattr(obj, "val") and obj.val else {}

            name = val.get("name") if isinstance(val, dict) else None
            description = val.get("description") if isinstance(val, dict) else None

            yield tsi.EvaluationReadRes(
                object_id=obj.object_id,
                digest=obj.digest,
                version_index=obj.version_index,
                created_at=obj.created_at,
                name=name,
                description=description,
                dataset=val.get("dataset", "") if isinstance(val, dict) else "",
                scorers=val.get("scorers", []) if isinstance(val, dict) else [],
                trials=val.get("trials", 1) if isinstance(val, dict) else 1,
                evaluation_name=(
                    val.get("evaluation_name") if isinstance(val, dict) else None
                ),
                evaluate_op=val.get("evaluate", "") if isinstance(val, dict) else "",
                predict_and_score_op=(
                    val.get("predict_and_score", "") if isinstance(val, dict) else ""
                ),
                summarize_op=val.get("summarize", "") if isinstance(val, dict) else "",
            )

    def evaluation_delete(
        self, req: tsi.EvaluationDeleteReq
    ) -> tsi.EvaluationDeleteRes:
        """Delete evaluation objects by delegating to obj_delete."""
        obj_delete_req = tsi.ObjDeleteReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )
        result = self.obj_delete(obj_delete_req)
        return tsi.EvaluationDeleteRes(num_deleted=result.num_deleted)

    # Model V2 API

    def model_create(self, req: tsi.ModelCreateReq) -> tsi.ModelCreateRes:
        """Create a model object.

        Args:
            req: ModelCreateReq containing project_id, name, description, source_code, and attributes

        Returns:
            ModelCreateRes with digest, object_id, version_index, and model_ref
        """
        # Store source code as a file
        source_file_req = tsi.FileCreateReq(
            project_id=req.project_id,
            name=object_creation_utils.OP_SOURCE_FILE_NAME,
            content=req.source_code.encode("utf-8"),
        )
        source_file_res = self.file_create(source_file_req)

        # Build the model object value structure
        model_val = object_creation_utils.build_model_val(
            name=req.name,
            description=req.description,
            source_file_digest=source_file_res.digest,
            attributes=req.attributes,
        )

        # Generate object_id based on name
        object_id = object_creation_utils.make_object_id(req.name, "Model")

        # Create the object
        obj_req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=req.project_id,
                object_id=object_id,
                val=model_val,
            )
        )
        obj_result = self.obj_create(obj_req)

        # Query back to get version_index with retry
        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=object_id,
            digest=obj_result.digest,
        )
        obj_read_res = self._obj_read_with_retry(
            obj_read_req, max_attempts=OBJ_READ_RETRY_ATTEMPTS
        )

        # Build model reference - external adapter will convert to external format
        model_ref = ri.InternalObjectRef(
            project_id=req.project_id,
            name=object_id,
            version=obj_result.digest,
        ).uri

        return tsi.ModelCreateRes(
            digest=obj_result.digest,
            object_id=object_id,
            version_index=obj_read_res.obj.version_index,
            model_ref=model_ref,
        )

    def model_read(self, req: tsi.ModelReadReq) -> tsi.ModelReadRes:
        """Read a model object.

        Args:
            req: ModelReadReq containing project_id, object_id, and digest

        Returns:
            ModelReadRes with all model details
        """
        # Read the object
        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
        )
        obj_read_res = self._obj_read_with_retry(obj_read_req)

        # Extract model properties from the val dict
        val = obj_read_res.obj.val
        name = val.get("name", req.object_id)
        description = val.get("description")

        # Get source code from file
        files = val.get("files", {})
        source_file_digest = files.get(object_creation_utils.OP_SOURCE_FILE_NAME)
        if not source_file_digest:
            raise ValueError(f"Model {req.object_id} has no source file")

        file_content_req = tsi.FileContentReadReq(
            project_id=req.project_id,
            digest=source_file_digest,
        )
        file_content_res = self._file_content_read_with_retry(file_content_req)
        source_code = file_content_res.content.decode("utf-8")

        # Extract additional attributes (exclude system fields)
        excluded_fields = {
            "_type",
            "_class_name",
            "_bases",
            "name",
            "description",
            "files",
        }
        attributes = {k: v for k, v in val.items() if k not in excluded_fields}

        return tsi.ModelReadRes(
            object_id=req.object_id,
            digest=req.digest,
            version_index=obj_read_res.obj.version_index,
            created_at=obj_read_res.obj.created_at,
            name=name,
            description=description,
            source_code=source_code,
            attributes=attributes if attributes else None,
        )

    def model_list(self, req: tsi.ModelListReq) -> Iterator[tsi.ModelReadRes]:
        """List model objects by delegating to objs_query with Model filtering."""
        obj_query_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=tsi.ObjectVersionFilter(base_object_classes=["Model"], is_op=False),
            limit=req.limit,
            offset=req.offset,
        )
        obj_query_res = self.objs_query(obj_query_req)

        for obj in obj_query_res.objs:
            # Build ModelReadRes from each object
            val = obj.val
            name = val.get("name", obj.object_id)
            description = val.get("description")

            # Get source code from file
            files = val.get("files", {})
            source_file_digest = files.get(object_creation_utils.OP_SOURCE_FILE_NAME)
            if source_file_digest:
                file_content_req = tsi.FileContentReadReq(
                    project_id=req.project_id,
                    digest=source_file_digest,
                )
                file_content_res = self._file_content_read_with_retry(file_content_req)
                source_code = file_content_res.content.decode("utf-8")
            else:
                source_code = ""

            # Extract additional attributes
            excluded_fields = {
                "_type",
                "_class_name",
                "_bases",
                "name",
                "description",
                "files",
            }
            attributes = {k: v for k, v in val.items() if k not in excluded_fields}

            yield tsi.ModelReadRes(
                object_id=obj.object_id,
                digest=obj.digest,
                version_index=obj.version_index,
                created_at=obj.created_at,
                name=name,
                description=description,
                source_code=source_code,
                attributes=attributes if attributes else None,
            )

    def model_delete(self, req: tsi.ModelDeleteReq) -> tsi.ModelDeleteRes:
        """Delete model objects by delegating to obj_delete.

        Args:
            req: ModelDeleteReq containing project_id, object_id, and optional digests

        Returns:
            ModelDeleteRes with the number of deleted versions
        """
        obj_delete_req = tsi.ObjDeleteReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )
        result = self.obj_delete(obj_delete_req)
        return tsi.ModelDeleteRes(num_deleted=result.num_deleted)

    def evaluation_run_create(
        self, req: tsi.EvaluationRunCreateReq
    ) -> tsi.EvaluationRunCreateRes:
        """Create an evaluation run as a call with special attributes."""
        evaluation_run_id = generate_id()

        # Create the evaluation run op
        op_create_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=constants.EVALUATION_RUN_OP_NAME,
            source_code=object_creation_utils.PLACEHOLDER_EVALUATION_EVALUATE_OP_SOURCE,
        )
        op_create_res = self.op_create(op_create_req)

        # Build the op ref
        op_ref = ri.InternalOpRef(
            project_id=req.project_id,
            name=constants.EVALUATION_RUN_OP_NAME,
            version=op_create_res.digest,
        )

        # Start a call to represent the evaluation run
        call_start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=req.project_id,
                id=evaluation_run_id,
                trace_id=evaluation_run_id,
                op_name=op_ref.uri,
                started_at=datetime.datetime.now(datetime.timezone.utc),
                attributes={
                    constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                        constants.EVALUATION_RUN_ATTR_KEY: "true",
                        constants.EVALUATION_RUN_EVALUATION_ATTR_KEY: req.evaluation,
                        constants.EVALUATION_RUN_MODEL_ATTR_KEY: req.model,
                    }
                },
                inputs={
                    "self": req.evaluation,
                    "model": req.model,
                },
            )
        )
        self.call_start(call_start_req)

        return tsi.EvaluationRunCreateRes(evaluation_run_id=evaluation_run_id)

    def evaluation_run_read(
        self, req: tsi.EvaluationRunReadReq
    ) -> tsi.EvaluationRunReadRes:
        """Read an evaluation run by reading the underlying call."""
        call_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.evaluation_run_id,
        )
        call_res = self.call_read(call_read_req)
        if (call := call_res.call) is None:
            raise NotFoundError(f"Evaluation run {req.evaluation_run_id} not found")

        attributes = call.attributes.get(constants.WEAVE_ATTRIBUTES_NAMESPACE, {})
        status = determine_call_status(call)

        return tsi.EvaluationRunReadRes(
            evaluation_run_id=call.id,
            evaluation=attributes.get(constants.EVALUATION_RUN_EVALUATION_ATTR_KEY, ""),
            model=attributes.get(constants.EVALUATION_RUN_MODEL_ATTR_KEY, ""),
            status=status,
            started_at=call.started_at,
            finished_at=call.ended_at,
            summary=call.summary,
        )

    def evaluation_run_list(
        self, req: tsi.EvaluationRunListReq
    ) -> Iterator[tsi.EvaluationRunReadRes]:
        """List evaluation runs by querying calls with evaluation_run attribute."""
        # Build query conditions to filter at database level
        conditions: list[tsi_query.Operand] = []

        # Filter for calls with evaluation_run attribute set to true
        conditions.append(
            tsi_query.EqOperation(
                eq_=[
                    tsi_query.GetFieldOperator(
                        get_field_=f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.EVALUATION_RUN_ATTR_KEY}"
                    ),
                    tsi_query.LiteralOperation(literal_="true"),
                ]
            )
        )

        # Apply additional filters if specified
        if req.filter:
            if req.filter.evaluations:
                conditions.append(
                    tsi_query.InOperation(
                        in_=[
                            tsi_query.GetFieldOperator(
                                get_field_=f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.EVALUATION_RUN_EVALUATION_ATTR_KEY}"
                            ),
                            [
                                tsi_query.LiteralOperation(literal_=eval_ref)
                                for eval_ref in req.filter.evaluations
                            ],
                        ]
                    )
                )
            if req.filter.models:
                conditions.append(
                    tsi_query.InOperation(
                        in_=[
                            tsi_query.GetFieldOperator(
                                get_field_=f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.EVALUATION_RUN_MODEL_ATTR_KEY}"
                            ),
                            [
                                tsi_query.LiteralOperation(literal_=model_ref)
                                for model_ref in req.filter.models
                            ],
                        ]
                    )
                )
            if req.filter.evaluation_run_ids:
                conditions.append(
                    tsi_query.InOperation(
                        in_=[
                            tsi_query.GetFieldOperator(get_field_="id"),
                            [
                                tsi_query.LiteralOperation(literal_=run_id)
                                for run_id in req.filter.evaluation_run_ids
                            ],
                        ]
                    )
                )

        # Combine all conditions with AND
        query = tsi.Query(expr_=tsi_query.AndOperation(and_=conditions))

        # Query for calls that have the evaluation_run attribute
        calls_query_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            query=query,
            limit=req.limit,
            offset=req.offset,
        )

        # Use calls_query_stream to avoid loading all calls into memory
        for call in self.calls_query_stream(calls_query_req):
            attributes = call.attributes.get(constants.WEAVE_ATTRIBUTES_NAMESPACE, {})
            status = determine_call_status(call)

            yield tsi.EvaluationRunReadRes(
                evaluation_run_id=call.id,
                evaluation=attributes.get(
                    constants.EVALUATION_RUN_EVALUATION_ATTR_KEY, ""
                ),
                model=attributes.get(constants.EVALUATION_RUN_MODEL_ATTR_KEY, ""),
                status=status,
                started_at=call.started_at,
                finished_at=call.ended_at,
                summary=call.summary,
            )

    def evaluation_run_delete(
        self, req: tsi.EvaluationRunDeleteReq
    ) -> tsi.EvaluationRunDeleteRes:
        """Delete evaluation runs by deleting the underlying calls."""
        calls_delete_req = tsi.CallsDeleteReq(
            project_id=req.project_id,
            call_ids=req.evaluation_run_ids,
            wb_user_id=req.wb_user_id,
        )
        res = self.calls_delete(calls_delete_req)
        return tsi.EvaluationRunDeleteRes(num_deleted=res.num_deleted)

    def evaluation_run_finish(
        self, req: tsi.EvaluationRunFinishReq
    ) -> tsi.EvaluationRunFinishRes:
        """Finish an evaluation run by ending the underlying call.

        This creates a summarize call as a child of the evaluation run,
        then ends both the summarize call and the evaluation run.

        Args:
            req: EvaluationRunFinishReq containing project_id, evaluation_run_id, and optional summary

        Returns:
            EvaluationRunFinishRes with success status
        """
        summary = req.summary or {}

        # Read the evaluation run call to get the evaluation reference
        evaluation_run_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.evaluation_run_id,
        )
        evaluation_run_call = self.call_read(evaluation_run_read_req).call
        evaluation_ref = None
        if evaluation_run_call and evaluation_run_call.inputs:
            evaluation_ref = evaluation_run_call.inputs.get("self")

        # Query all predict_and_score children to compute means
        # (Do this first so we can use the same data for both summarize and evaluation_run)
        calls_query_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            filter=tsi.CallsFilter(
                parent_ids=[req.evaluation_run_id],
            ),
            columns=["output", "op_name"],
        )

        # Collect outputs and scores from all predict_and_score calls
        model_outputs = []
        scorer_outputs_by_name: dict[str, list[float]] = {}

        for call in self.calls_query_stream(calls_query_req):
            # Check if this is a predict_and_score call
            if not tsc.op_name_matches(
                call.op_name, constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME
            ):
                continue

            if call.output is None or not isinstance(call.output, dict):
                continue

            # Extract model output
            if (model_output := call.output.get("output")) is not None:
                model_outputs.append(model_output)

            # Extract scores
            scores = call.output.get("scores", {})
            if not isinstance(scores, dict):
                continue

            for scorer_name, score_value in scores.items():
                if scorer_name not in scorer_outputs_by_name:
                    scorer_outputs_by_name[scorer_name] = []
                # Only add numeric scores for mean calculation
                if isinstance(score_value, float):
                    scorer_outputs_by_name[scorer_name].append(float(score_value))

        # Build the evaluation run output with means
        eval_output = {}

        # Add scorer outputs
        for scorer_name, scores in scorer_outputs_by_name.items():
            if scores:
                eval_output[scorer_name] = {"mean": sum(scores) / len(scores)}

        # Add model outputs
        if model_outputs:
            try:
                numeric_outputs = [
                    float(o) for o in model_outputs if isinstance(o, (int, float))
                ]
                if numeric_outputs:
                    eval_output["output"] = {
                        "mean": sum(numeric_outputs) / len(numeric_outputs)
                    }
            except (ValueError, TypeError):
                pass

        # Create a summarize call as a child of the evaluation run
        summarize_id = generate_id()
        summarize_start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=req.project_id,
                id=summarize_id,
                trace_id=req.evaluation_run_id,
                parent_id=req.evaluation_run_id,
                op_name=constants.EVALUATION_SUMMARIZE_OP_NAME,
                started_at=datetime.datetime.now(datetime.timezone.utc),
                attributes={},
                inputs={
                    "self": evaluation_ref,
                },
                wb_user_id=req.wb_user_id,
            )
        )
        self.call_start(summarize_start_req)

        # End the summarize call with the same output as evaluation_run
        summarize_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=summarize_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output=eval_output,
                summary={},
            )
        )
        self.call_end(summarize_end_req)

        # End the evaluation run call
        call_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=req.evaluation_run_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output=eval_output,
                summary=summary,
            )
        )
        self.call_end(call_end_req)
        return tsi.EvaluationRunFinishRes(success=True)

    # Prediction V2 API

    def prediction_create(
        self, req: tsi.PredictionCreateReq
    ) -> tsi.PredictionCreateRes:
        """Create a prediction as a call with special attributes.

        Args:
            req: PredictionCreateReq containing project_id, model, inputs, and output

        Returns:
            PredictionCreateRes with the prediction_id
        """
        prediction_id = generate_id()

        # Determine trace_id and parent_id based on evaluation_run_id
        if req.evaluation_run_id:
            # If evaluation_run_id is provided, create a predict_and_score parent call
            trace_id = req.evaluation_run_id
            predict_and_score_id = generate_id()

            # Read the evaluation run call to get the evaluation reference
            evaluation_run_read_req = tsi.CallReadReq(
                project_id=req.project_id,
                id=req.evaluation_run_id,
            )
            eval_run_read_res = self.call_read(evaluation_run_read_req)

            call = eval_run_read_res.call
            if call is None:
                raise NotFoundError(f"Evaluation run {req.evaluation_run_id} not found")
            evaluation_ref = call.inputs.get("self")

            # Create the predict_and_score op
            predict_and_score_op_req = tsi.OpCreateReq(
                project_id=req.project_id,
                name=constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
                source_code=object_creation_utils.PLACEHOLDER_EVALUATION_PREDICT_AND_SCORE_OP_SOURCE,
            )
            predict_and_score_op_res = self.op_create(predict_and_score_op_req)

            # Build the predict_and_score op ref
            predict_and_score_op_ref = ri.InternalOpRef(
                project_id=req.project_id,
                name=constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
                version=predict_and_score_op_res.digest,
            )

            # Create the predict_and_score call as a child of the evaluation run
            predict_and_score_start_req = tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=req.project_id,
                    id=predict_and_score_id,
                    trace_id=trace_id,
                    parent_id=req.evaluation_run_id,
                    op_name=predict_and_score_op_ref.uri,
                    started_at=datetime.datetime.now(datetime.timezone.utc),
                    attributes={
                        constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                            constants.EVALUATION_RUN_PREDICT_CALL_ID_ATTR_KEY: prediction_id,
                        }
                    },
                    inputs={
                        "self": evaluation_ref,
                        "model": req.model,
                        "example": req.inputs,
                    },
                    wb_user_id=req.wb_user_id,
                )
            )
            self.call_start(predict_and_score_start_req)

            # The prediction will be a child of predict_and_score
            parent_id = predict_and_score_id
        else:
            # Standalone prediction (not part of an evaluation)
            trace_id = prediction_id
            parent_id = None

        # Parse the model ref to get the model name
        try:
            model_ref = ri.parse_internal_uri(req.model)
            if isinstance(model_ref, (ri.InternalObjectRef, ri.InternalOpRef)):
                model_name = model_ref.name
            else:
                # Fallback to default if not an object/op ref
                model_name = "Model"
        except ri.InvalidInternalRef:
            # Fallback to default if parsing fails
            model_name = "Model"

        # Create the predict op with the model-specific name
        predict_op_name = f"{model_name}.predict"
        predict_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=predict_op_name,
            source_code=object_creation_utils.PLACEHOLDER_MODEL_PREDICT_OP_SOURCE,
        )
        predict_op_res = self.op_create(predict_op_req)

        # Build the predict op ref
        predict_op_ref = ri.InternalOpRef(
            project_id=req.project_id,
            name=predict_op_name,
            version=predict_op_res.digest,
        )

        # Start a call to represent the prediction
        prediction_attributes = {
            constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                constants.PREDICTION_ATTR_KEY: "true",
                constants.PREDICTION_MODEL_ATTR_KEY: req.model,
            }
        }
        # Store evaluation_run_id as attribute if provided
        if req.evaluation_run_id:
            prediction_attributes[constants.WEAVE_ATTRIBUTES_NAMESPACE][
                constants.PREDICTION_EVALUATION_RUN_ID_ATTR_KEY
            ] = req.evaluation_run_id

        call_start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=req.project_id,
                id=prediction_id,
                trace_id=trace_id,
                parent_id=parent_id,
                op_name=predict_op_ref.uri,
                started_at=datetime.datetime.now(datetime.timezone.utc),
                attributes=prediction_attributes,
                inputs={
                    "self": req.model,
                    "inputs": req.inputs,
                },
                wb_user_id=req.wb_user_id,
            )
        )
        self.call_start(call_start_req)

        # End the call immediately with the output
        call_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=prediction_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output=req.output,
                summary={},
            )
        )
        self.call_end(call_end_req)

        return tsi.PredictionCreateRes(prediction_id=prediction_id)

    def prediction_read(self, req: tsi.PredictionReadReq) -> tsi.PredictionReadRes:
        """Read a prediction by reading the underlying call.

        Args:
            req: PredictionReadReq containing project_id and prediction_id

        Returns:
            PredictionReadRes with all prediction details

        Raises:
            NotFoundError: If the prediction is not found
        """
        call_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.prediction_id,
        )
        call_res = self.call_read(call_read_req)

        call = call_res.call
        if call is None:
            raise NotFoundError(f"Prediction {req.prediction_id} not found")

        attributes = call.attributes.get(constants.WEAVE_ATTRIBUTES_NAMESPACE, {})

        # Get evaluation_run_id from attributes (preferred), fallback to parent traversal for backwards compatibility
        evaluation_run_id = attributes.get(
            constants.PREDICTION_EVALUATION_RUN_ID_ATTR_KEY
        )
        if evaluation_run_id is None and call.parent_id:
            # Fallback: If the parent is a predict_and_score call, get the evaluation_run_id from its parent
            parent_read_req = tsi.CallReadReq(
                project_id=req.project_id,
                id=call.parent_id,
            )
            parent_res = self.call_read(parent_read_req)
            if parent_res.call and tsc.op_name_matches(
                parent_res.call.op_name,
                constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
            ):
                evaluation_run_id = parent_res.call.parent_id

        return tsi.PredictionReadRes(
            prediction_id=call.id,
            model=attributes.get(constants.PREDICTION_MODEL_ATTR_KEY, ""),
            inputs=tsc.get_prediction_inputs(call.inputs),
            output=call.output,
            evaluation_run_id=evaluation_run_id,
            wb_user_id=call.wb_user_id,
        )

    def prediction_list(
        self, req: tsi.PredictionListReq
    ) -> Iterator[tsi.PredictionReadRes]:
        """List predictions by querying calls with prediction attribute.

        Args:
            req: PredictionListReq containing project_id, limit, and offset

        Yields:
            PredictionReadRes for each prediction found
        """
        # Build query conditions to filter at database level
        conditions: list[tsi_query.Operand] = []

        # Filter for calls with prediction attribute set to true
        conditions.append(
            tsi_query.EqOperation(
                eq_=[
                    tsi_query.GetFieldOperator(
                        get_field_=f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.PREDICTION_ATTR_KEY}"
                    ),
                    tsi_query.LiteralOperation(literal_="true"),
                ]
            )
        )

        # Filter by evaluation_run_id if provided
        if req.evaluation_run_id:
            conditions.append(
                tsi_query.EqOperation(
                    eq_=[
                        tsi_query.GetFieldOperator(
                            get_field_=f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.PREDICTION_EVALUATION_RUN_ID_ATTR_KEY}"
                        ),
                        tsi_query.LiteralOperation(literal_=req.evaluation_run_id),
                    ]
                )
            )

        # Combine all conditions with AND (or use single condition if only one)
        if len(conditions) == 1:
            query = tsi.Query(expr_=conditions[0])
        else:
            query = tsi.Query(expr_=tsi_query.AndOperation(and_=conditions))

        # Query for calls that have the prediction attribute
        calls_query_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            query=query,
            limit=req.limit,
            offset=req.offset,
        )

        # Yield predictions
        for call in self.calls_query_stream(calls_query_req):
            attributes = call.attributes.get(constants.WEAVE_ATTRIBUTES_NAMESPACE, {})

            # Get evaluation_run_id from attributes (preferred), fallback to parent traversal for backwards compatibility
            evaluation_run_id = attributes.get(
                constants.PREDICTION_EVALUATION_RUN_ID_ATTR_KEY
            )
            if evaluation_run_id is None and call.parent_id:
                # Fallback: If the parent is a predict_and_score call, get the evaluation_run_id from its parent
                parent_read_req = tsi.CallReadReq(
                    project_id=req.project_id,
                    id=call.parent_id,
                )
                parent_res = self.call_read(parent_read_req)
                if parent_res.call and tsc.op_name_matches(
                    parent_res.call.op_name,
                    constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
                ):
                    evaluation_run_id = parent_res.call.parent_id

            yield tsi.PredictionReadRes(
                prediction_id=call.id,
                model=attributes.get(constants.PREDICTION_MODEL_ATTR_KEY, ""),
                inputs=tsc.get_prediction_inputs(call.inputs),
                output=call.output,
                evaluation_run_id=evaluation_run_id,
                wb_user_id=call.wb_user_id,
            )

    def prediction_delete(
        self, req: tsi.PredictionDeleteReq
    ) -> tsi.PredictionDeleteRes:
        """Delete predictions by deleting the underlying calls.

        Args:
            req: PredictionDeleteReq containing project_id and prediction_ids

        Returns:
            PredictionDeleteRes with the number of deleted predictions
        """
        calls_delete_req = tsi.CallsDeleteReq(
            project_id=req.project_id,
            call_ids=req.prediction_ids,
            wb_user_id=req.wb_user_id,
        )
        res = self.calls_delete(calls_delete_req)
        return tsi.PredictionDeleteRes(num_deleted=res.num_deleted)

    def prediction_finish(
        self, req: tsi.PredictionFinishReq
    ) -> tsi.PredictionFinishRes:
        """Finish a prediction by ending the underlying call.

        If the prediction is part of an evaluation (has a predict_and_score parent),
        this will also finish the predict_and_score parent call.

        Args:
            req: PredictionFinishReq containing project_id and prediction_id

        Returns:
            PredictionFinishRes with success status
        """
        # Read the prediction to check if it has a parent (predict_and_score call)
        prediction_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.prediction_id,
        )
        prediction_res = self.call_read(prediction_read_req)

        # Finish the prediction call
        call_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=req.prediction_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output=None,
                summary={},
            )
        )
        self.call_end(call_end_req)

        # If this prediction has a parent (predict_and_score call), finish that too
        prediction_call = prediction_res.call

        # If there is no parent, or the parent is not a predict_and_score call,
        # this is a regular prediction and we can return success
        if not prediction_call or not prediction_call.parent_id:
            return tsi.PredictionFinishRes(success=True)

        parent_id = prediction_call.parent_id

        parent_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=parent_id,
        )
        parent_res = self.call_read(parent_read_req)
        parent_call = parent_res.call
        if not parent_call or not tsc.op_name_matches(
            parent_call.op_name,
            constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
        ):
            return tsi.PredictionFinishRes(success=True)

        # == After here, we assume the parent is a predict_and_score call ==

        # Build the scores dict by querying all score children of predict_and_score
        scores_dict = {}

        # Build query to filter for score calls at database level
        score_query = tsi.Query(
            expr_=tsi_query.EqOperation(
                eq_=[
                    tsi_query.GetFieldOperator(
                        get_field_=f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.SCORE_ATTR_KEY}"
                    ),
                    tsi_query.LiteralOperation(literal_="true"),
                ]
            )
        )

        calls_query_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            filter=tsi.CallsFilter(
                parent_ids=[parent_id],
            ),
            query=score_query,
            columns=["output", "attributes"],
        )

        for score_call in self.calls_query_stream(calls_query_req):
            if score_call.output is None:
                continue

            # Get scorer name from the scorer ref in attributes
            weave_attrs = score_call.attributes.get(
                constants.WEAVE_ATTRIBUTES_NAMESPACE, {}
            )
            scorer_ref = weave_attrs.get(constants.SCORE_SCORER_ATTR_KEY)

            # Extract scorer name from ref (e.g., "weave:///entity/project/Scorer:digest" -> "Scorer")
            scorer_name = "unknown"
            if scorer_ref and isinstance(scorer_ref, str):
                # Parse the weave:// URI to get the object name
                parts = scorer_ref.split("/")
                if parts:
                    # Get the last part which should be like "Scorer:digest"
                    name_and_digest = parts[-1]
                    if ":" in name_and_digest:
                        scorer_name = name_and_digest.split(":")[0]

            scores_dict[scorer_name] = score_call.output

        # Calculate model latency from the prediction call's timestamps
        model_latency = None
        if prediction_call.started_at and prediction_call.ended_at:
            latency_seconds = (
                prediction_call.ended_at - prediction_call.started_at
            ).total_seconds()
            model_latency = {"mean": latency_seconds}

        # Finish the predict_and_score parent call with proper output
        parent_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=parent_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output={
                    "output": prediction_call.output,
                    "scores": scores_dict,
                    "model_latency": model_latency,
                },
                summary={},
            )
        )
        self.call_end(parent_end_req)

        return tsi.PredictionFinishRes(success=True)

    # Score V2 API

    def score_create(self, req: tsi.ScoreCreateReq) -> tsi.ScoreCreateRes:
        """Create a score as a call with special attributes.

        Args:
            req: ScoreCreateReq containing project_id, prediction_id, scorer, and value

        Returns:
            ScoreCreateRes with the score_id
        """
        score_id = generate_id()

        # Read the prediction to get its inputs and output
        prediction_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.prediction_id,
        )
        prediction_res = self.call_read(prediction_read_req)

        # Extract inputs and output from the prediction call
        prediction_inputs = {}
        prediction_output = None
        prediction_call = prediction_res.call
        if prediction_call:
            # The prediction call has inputs structured as {"self": model_ref, "inputs": actual_inputs}
            # We want just the actual_inputs part
            if isinstance(prediction_call.inputs, dict):
                prediction_inputs = prediction_call.inputs.get("inputs", {})
            prediction_output = prediction_call.output

        # Determine trace_id and parent_id based on evaluation_run_id
        if req.evaluation_run_id:
            # If evaluation_run_id is provided, find the prediction's parent (predict_and_score call)
            # and make this score a sibling of the prediction
            trace_id = req.evaluation_run_id

            if prediction_call and prediction_call.parent_id:
                # Use the prediction's parent as this score's parent
                parent_id = prediction_call.parent_id
            else:
                # Fallback: make it a direct child of the evaluation_run
                parent_id = req.evaluation_run_id
        else:
            # Standalone score (not part of an evaluation)
            trace_id = score_id
            parent_id = None

        # Parse the scorer ref to get the scorer name
        scorer_ref = ri.parse_internal_uri(req.scorer)
        if not isinstance(scorer_ref, ri.InternalObjectRef):
            raise TypeError(f"Invalid scorer ref: {req.scorer}")
        scorer_name = scorer_ref.name

        # Create the score op with scorer-specific name
        score_op_name = f"{scorer_name}.score"
        score_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=score_op_name,
            source_code=object_creation_utils.PLACEHOLDER_SCORER_SCORE_OP_SOURCE,
        )
        score_op_res = self.op_create(score_op_req)

        # Build the score op ref
        score_op_ref = ri.InternalOpRef(
            project_id=req.project_id,
            name=score_op_name,
            version=score_op_res.digest,
        )

        # Start a call to represent the score
        score_attributes = {
            constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                constants.SCORE_ATTR_KEY: "true",
                constants.SCORE_PREDICTION_ID_ATTR_KEY: req.prediction_id,
                constants.SCORE_SCORER_ATTR_KEY: req.scorer,
            }
        }
        # Store evaluation_run_id as attribute if provided
        if req.evaluation_run_id:
            score_attributes[constants.WEAVE_ATTRIBUTES_NAMESPACE][
                constants.SCORE_EVALUATION_RUN_ID_ATTR_KEY
            ] = req.evaluation_run_id

        call_start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=req.project_id,
                id=score_id,
                trace_id=trace_id,
                parent_id=parent_id,
                op_name=score_op_ref.uri,
                started_at=datetime.datetime.now(datetime.timezone.utc),
                attributes=score_attributes,
                inputs={
                    "self": req.scorer,
                    "inputs": prediction_inputs,
                    "output": prediction_output,
                },
                wb_user_id=req.wb_user_id,
            )
        )
        self.call_start(call_start_req)

        # End the call immediately with the score value
        call_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=score_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output=req.value,
                summary={},
            )
        )
        self.call_end(call_end_req)

        # Also create feedback on the prediction (Model.predict) call
        # This makes the score visible in the UI attached to the prediction
        prediction_call_ref = ri.InternalCallRef(
            project_id=req.project_id,
            id=req.prediction_id,
        )

        # Get wb_user_id from request or fall back to prediction's wb_user_id or default
        wb_user_id = (
            req.wb_user_id
            or (prediction_call.wb_user_id if prediction_call else None)
            or "unknown"
        )

        feedback_req = tsi.FeedbackCreateReq(
            project_id=req.project_id,
            weave_ref=prediction_call_ref.uri,
            feedback_type=f"{RUNNABLE_FEEDBACK_TYPE_PREFIX}.{scorer_name}",
            payload={"output": req.value},
            runnable_ref=req.scorer,
            wb_user_id=wb_user_id,
        )
        self.feedback_create(feedback_req)

        return tsi.ScoreCreateRes(score_id=score_id)

    def score_read(self, req: tsi.ScoreReadReq) -> tsi.ScoreReadRes:
        """Read a score by reading the underlying call.

        Args:
            req: ScoreReadReq containing project_id and score_id

        Returns:
            ScoreReadRes with all score details

        Raises:
            NotFoundError: If the score is not found
        """
        call_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.score_id,
        )
        call_res = self.call_read(call_read_req)

        if call_res.call is None:
            raise NotFoundError(f"Score {req.score_id} not found")

        call = call_res.call
        attributes = call.attributes.get(constants.WEAVE_ATTRIBUTES_NAMESPACE, {})

        # Extract score value from output
        # The output is stored directly as the numeric value
        value = call.output if call.output is not None else 0.0

        # Get evaluation_run_id from attributes (preferred), fallback to parent traversal for backwards compatibility
        evaluation_run_id = attributes.get(constants.SCORE_EVALUATION_RUN_ID_ATTR_KEY)
        if evaluation_run_id is None and call.parent_id:
            # Fallback: If the parent is a predict_and_score call, get the evaluation_run_id from its parent
            parent_read_req = tsi.CallReadReq(
                project_id=req.project_id,
                id=call.parent_id,
            )
            parent_res = self.call_read(parent_read_req)
            if parent_res.call and tsc.op_name_matches(
                parent_res.call.op_name,
                constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
            ):
                evaluation_run_id = parent_res.call.parent_id

        return tsi.ScoreReadRes(
            score_id=call.id,
            scorer=attributes.get(constants.SCORE_SCORER_ATTR_KEY, ""),
            value=value,
            evaluation_run_id=evaluation_run_id,
            wb_user_id=call.wb_user_id,
        )

    def score_list(self, req: tsi.ScoreListReq) -> Iterator[tsi.ScoreReadRes]:
        """List scores by querying calls with score attribute.

        Args:
            req: ScoreListReq containing project_id, limit, and offset

        Yields:
            ScoreReadRes for each score found
        """
        # Build query conditions to filter at database level
        conditions: list[tsi_query.Operand] = []

        # Filter for calls with score attribute set to true
        conditions.append(
            tsi_query.EqOperation(
                eq_=[
                    tsi_query.GetFieldOperator(
                        get_field_=f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.SCORE_ATTR_KEY}"
                    ),
                    tsi_query.LiteralOperation(literal_="true"),
                ]
            )
        )

        # Filter by evaluation_run_id if provided
        if req.evaluation_run_id:
            conditions.append(
                tsi_query.EqOperation(
                    eq_=[
                        tsi_query.GetFieldOperator(
                            get_field_=f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.SCORE_EVALUATION_RUN_ID_ATTR_KEY}"
                        ),
                        tsi_query.LiteralOperation(literal_=req.evaluation_run_id),
                    ]
                )
            )

        # Combine all conditions with AND (or use single condition if only one)
        if len(conditions) == 1:
            query = tsi.Query(expr_=conditions[0])
        else:
            query = tsi.Query(expr_=tsi_query.AndOperation(and_=conditions))

        # Query for calls that have the score attribute
        calls_query_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            query=query,
            limit=req.limit,
            offset=req.offset,
        )

        # Yield scores
        for call in self.calls_query_stream(calls_query_req):
            attributes = call.attributes.get(constants.WEAVE_ATTRIBUTES_NAMESPACE, {})
            value = call.output if call.output is not None else 0.0

            # Get evaluation_run_id from attributes (preferred), fallback to parent traversal for backwards compatibility
            evaluation_run_id = attributes.get(
                constants.SCORE_EVALUATION_RUN_ID_ATTR_KEY
            )
            if evaluation_run_id is None and call.parent_id:
                # Fallback: If the parent is a predict_and_score call, get the evaluation_run_id from its parent
                parent_read_req = tsi.CallReadReq(
                    project_id=req.project_id,
                    id=call.parent_id,
                )
                parent_res = self.call_read(parent_read_req)
                if parent_res.call and tsc.op_name_matches(
                    parent_res.call.op_name,
                    constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
                ):
                    evaluation_run_id = parent_res.call.parent_id

            yield tsi.ScoreReadRes(
                score_id=call.id,
                scorer=attributes.get(constants.SCORE_SCORER_ATTR_KEY, ""),
                value=value,
                evaluation_run_id=evaluation_run_id,
                wb_user_id=call.wb_user_id,
            )

    def score_delete(self, req: tsi.ScoreDeleteReq) -> tsi.ScoreDeleteRes:
        """Delete scores by deleting the underlying calls.

        Args:
            req: ScoreDeleteReq containing project_id and score_ids

        Returns:
            ScoreDeleteRes with the number of deleted scores
        """
        calls_delete_req = tsi.CallsDeleteReq(
            project_id=req.project_id,
            call_ids=req.score_ids,
            wb_user_id=req.wb_user_id,
        )
        res = self.calls_delete(calls_delete_req)
        return tsi.ScoreDeleteRes(num_deleted=res.num_deleted)

    def eval_results_query(
        self, req: tsi.EvalResultsQueryReq
    ) -> tsi.EvalResultsQueryRes:
        """Return grouped prediction/trial/score data for evaluation results."""
        eval_root_ids = eval_helpers.resolve_eval_root_ids(req)
        if not eval_root_ids:
            empty_summary = tsi.EvalResultsSummaryRes() if req.include_summary else None
            return tsi.EvalResultsQueryRes(
                rows=[], total_rows=0, summary=empty_summary, warnings=[]
            )
        all_calls = list(
            self._calls_query_stream_for_eval_subtree(req.project_id, eval_root_ids)
        )
        return eval_helpers.eval_results_query(self, req, eval_root_ids, all_calls)

    def evaluate_model(self, req: tsi.EvaluateModelReq) -> tsi.EvaluateModelRes:
        if self._evaluate_model_dispatcher is None:
            raise ValueError("Evaluate model dispatcher is not set")
        if req.wb_user_id is None:
            raise ValueError("wb_user_id is required")
        call_id = generate_id()

        self._evaluate_model_dispatcher.dispatch(
            EvaluateModelArgs(
                project_id=req.project_id,
                evaluation_ref=req.evaluation_ref,
                model_ref=req.model_ref,
                wb_user_id=req.wb_user_id,
                evaluation_call_id=call_id,
            )
        )
        return tsi.EvaluateModelRes(call_id=call_id)

    def evaluation_status(
        self, req: tsi.EvaluationStatusReq
    ) -> tsi.EvaluationStatusRes:
        return evaluation_status(self, req)

    def calls_score(self, req: tsi.CallsScoreReq) -> tsi.CallsScoreRes:
        """Enqueue scoring jobs for a list of calls.

        Publishes the request to Kafka, where it will be consumed by the
        call_scoring_worker and applied asynchronously.
        """
        if self.kafka_producer is None:
            raise ValueError("Kafka producer is not set")

        self.kafka_producer.produce_score_calls(req)

        return tsi.CallsScoreRes()
