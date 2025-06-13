import uuid
from typing import Dict, Optional

from weave.trace_server.interface.evaluations import (
    TraceServerEvaluationInterfaceMixin,
)
from weave.trace_server.interface.evaluations.EvaluationSummary import (
    CreateEvaluationSummaryReq,
    CreateEvaluationSummaryRes,
    DeleteEvaluationSummaryReq,
    DeleteEvaluationSummaryRes,
    EvaluationSummary,
    GetEvaluationSummaryReq,
    GetEvaluationSummaryRes,
    UpdateEvaluationSummaryReq,
    UpdateEvaluationSummaryRes,
)
from weave.trace_server.interface.evaluations.ExampleLabel import (
    CreateExampleLabelReq,
    CreateExampleLabelRes,
    DeleteExampleLabelReq,
    DeleteExampleLabelRes,
    ExampleLabel,
    GetExampleLabelReq,
    GetExampleLabelRes,
    UpdateExampleLabelReq,
    UpdateExampleLabelRes,
)
from weave.trace_server.interface.evaluations.GenerationResult import (
    CreateGenerationResultReq,
    CreateGenerationResultRes,
    DeleteGenerationResultReq,
    DeleteGenerationResultRes,
    GenerationResult,
    GetGenerationResultReq,
    GetGenerationResultRes,
    UpdateGenerationResultReq,
    UpdateGenerationResultRes,
)
from weave.trace_server.interface.evaluations.InputPayload import (
    CreateInputPayloadReq,
    CreateInputPayloadRes,
    DeleteInputPayloadReq,
    DeleteInputPayloadRes,
    GetInputPayloadReq,
    GetInputPayloadRes,
    InputPayload,
    UpdateInputPayloadReq,
    UpdateInputPayloadRes,
)
from weave.trace_server.interface.evaluations.ModelClass import (
    CreateModelClassReq,
    CreateModelClassRes,
    DeleteModelClassReq,
    DeleteModelClassRes,
    GetModelClassReq,
    GetModelClassRes,
    ModelClass,
    UpdateModelClassReq,
    UpdateModelClassRes,
)
from weave.trace_server.interface.evaluations.ModelInstance import (
    CreateModelInstanceReq,
    CreateModelInstanceRes,
    DeleteModelInstanceReq,
    DeleteModelInstanceRes,
    GetModelInstanceReq,
    GetModelInstanceRes,
    ModelInstance,
    UpdateModelInstanceReq,
    UpdateModelInstanceRes,
)
from weave.trace_server.interface.evaluations.ScorerClass import (
    CreateScorerClassReq,
    CreateScorerClassRes,
    DeleteScorerClassReq,
    DeleteScorerClassRes,
    GetScorerClassReq,
    GetScorerClassRes,
    ScorerClass,
    UpdateScorerClassReq,
    UpdateScorerClassRes,
)
from weave.trace_server.interface.evaluations.ScoreResult import (
    CreateScoreResultReq,
    CreateScoreResultRes,
    DeleteScoreResultReq,
    DeleteScoreResultRes,
    GetScoreResultReq,
    GetScoreResultRes,
    ScoreResult,
    UpdateScoreResultReq,
    UpdateScoreResultRes,
)
from weave.trace_server.interface.evaluations.ScorerInstance import (
    CreateScorerInstanceReq,
    CreateScorerInstanceRes,
    DeleteScorerInstanceReq,
    DeleteScorerInstanceRes,
    GetScorerInstanceReq,
    GetScorerInstanceRes,
    ScorerInstance,
    UpdateScorerInstanceReq,
    UpdateScorerInstanceRes,
)
from weave.trace_server.interface.evaluations.TaskDefinition import (
    CreateTaskDefinitionReq,
    CreateTaskDefinitionRes,
    DeleteTaskDefinitionReq,
    DeleteTaskDefinitionRes,
    GetTaskDefinitionReq,
    GetTaskDefinitionRes,
    TaskDefinition,
    UpdateTaskDefinitionReq,
    UpdateTaskDefinitionRes,
)
from weave.trace_server.interface.evaluations.TaskExample import (
    CreateTaskExampleReq,
    CreateTaskExampleRes,
    DeleteTaskExampleReq,
    DeleteTaskExampleRes,
    GetTaskExampleReq,
    GetTaskExampleRes,
    TaskExample,
    UpdateTaskExampleReq,
    UpdateTaskExampleRes,
)


class InMemoryStore:
    """Generic in-memory store for entities"""

    def __init__(self):
        self.data: Dict[str, dict] = {}
        self.deleted: set = set()

    def create(self, id: str, data: dict):
        if id in self.data:
            raise ValueError(f"Entity with id {id} already exists")
        self.data[id] = data
        self.deleted.discard(id)

    def get(self, id: str) -> Optional[dict]:
        if id in self.deleted or id not in self.data:
            return None
        return self.data.get(id)

    def update(self, id: str, updates: dict):
        if id in self.deleted or id not in self.data:
            raise ValueError(f"Entity with id {id} not found")
        self.data[id].update(updates)

    def delete(self, id: str):
        if id not in self.data:
            raise ValueError(f"Entity with id {id} not found")
        self.deleted.add(id)

    def exists(self, id: str) -> bool:
        return id in self.data and id not in self.deleted


class SampleImplementation(TraceServerEvaluationInterfaceMixin):
    def __init__(self):
        # Initialize stores for each entity type
        self.model_classes = InMemoryStore()
        self.model_instances = InMemoryStore()
        self.input_payloads = InMemoryStore()
        self.generation_results = InMemoryStore()
        self.task_definitions = InMemoryStore()
        self.task_examples = InMemoryStore()
        self.scorer_classes = InMemoryStore()
        self.scorer_instances = InMemoryStore()
        self.score_results = InMemoryStore()
        self.example_labels = InMemoryStore()
        self.evaluation_summaries = InMemoryStore()

    def _generate_id(self) -> str:
        return str(uuid.uuid4())

    # ModelClass methods
    async def async_create_model_class(
        self, req: CreateModelClassReq
    ) -> CreateModelClassRes:
        id = self._generate_id()
        data = req.properties.model_dump()
        data["id"] = id
        self.model_classes.create(id, data)
        return CreateModelClassRes(id=id)

    async def async_get_model_class(self, req: GetModelClassReq) -> GetModelClassRes:
        data = self.model_classes.get(req.id)
        if data is None:
            raise ValueError(f"ModelClass {req.id} not found")
        return GetModelClassRes(result=ModelClass(**data))

    async def async_update_model_class(
        self, req: UpdateModelClassReq
    ) -> UpdateModelClassRes:
        updates = req.updates.model_dump(exclude_unset=True)
        self.model_classes.update(req.id, updates)
        return UpdateModelClassRes()

    async def async_delete_model_class(
        self, req: DeleteModelClassReq
    ) -> DeleteModelClassRes:
        self.model_classes.delete(req.id)
        return DeleteModelClassRes()

    # ModelInstance methods
    async def async_create_model_instance(
        self, req: CreateModelInstanceReq
    ) -> CreateModelInstanceRes:
        # Verify model class exists
        if not self.model_classes.exists(req.properties.model_class_id):
            raise ValueError(f"ModelClass {req.properties.model_class_id} not found")

        id = self._generate_id()
        data = req.properties.model_dump()
        data["id"] = id
        self.model_instances.create(id, data)
        return CreateModelInstanceRes(id=id)

    async def async_get_model_instance(
        self, req: GetModelInstanceReq
    ) -> GetModelInstanceRes:
        data = self.model_instances.get(req.id)
        if data is None:
            raise ValueError(f"ModelInstance {req.id} not found")
        return GetModelInstanceRes(result=ModelInstance(**data))

    async def async_update_model_instance(
        self, req: UpdateModelInstanceReq
    ) -> UpdateModelInstanceRes:
        updates = req.updates.model_dump(exclude_unset=True)
        self.model_instances.update(req.id, updates)
        return UpdateModelInstanceRes()

    async def async_delete_model_instance(
        self, req: DeleteModelInstanceReq
    ) -> DeleteModelInstanceRes:
        self.model_instances.delete(req.id)
        return DeleteModelInstanceRes()

    # InputPayload methods
    async def async_create_input_payload(
        self, req: CreateInputPayloadReq
    ) -> CreateInputPayloadRes:
        id = self._generate_id()
        data = req.properties.model_dump()
        data["id"] = id
        self.input_payloads.create(id, data)
        return CreateInputPayloadRes(id=id)

    async def async_get_input_payload(
        self, req: GetInputPayloadReq
    ) -> GetInputPayloadRes:
        data = self.input_payloads.get(req.id)
        if data is None:
            raise ValueError(f"InputPayload {req.id} not found")
        return GetInputPayloadRes(InputPayload=InputPayload(**data))

    async def async_update_input_payload(
        self, req: UpdateInputPayloadReq
    ) -> UpdateInputPayloadRes:
        updates = req.updates.model_dump(exclude_unset=True)
        self.input_payloads.update(req.id, updates)
        return UpdateInputPayloadRes()

    async def async_delete_input_payload(
        self, req: DeleteInputPayloadReq
    ) -> DeleteInputPayloadRes:
        self.input_payloads.delete(req.id)
        return DeleteInputPayloadRes()

    # GenerationResult methods
    async def async_create_generation_result(
        self, req: CreateGenerationResultReq
    ) -> CreateGenerationResultRes:
        # Verify references exist
        if not self.model_instances.exists(req.properties.model_instance_id):
            raise ValueError(
                f"ModelInstance {req.properties.model_instance_id} not found"
            )
        if not self.input_payloads.exists(req.properties.input_payload_id):
            raise ValueError(
                f"InputPayload {req.properties.input_payload_id} not found"
            )

        id = self._generate_id()
        data = req.properties.model_dump()
        data["id"] = id
        self.generation_results.create(id, data)
        return CreateGenerationResultRes(id=id)

    async def async_get_generation_result(
        self, req: GetGenerationResultReq
    ) -> GetGenerationResultRes:
        data = self.generation_results.get(req.id)
        if data is None:
            raise ValueError(f"GenerationResult {req.id} not found")
        return GetGenerationResultRes(GenerationResult=GenerationResult(**data))

    async def async_update_generation_result(
        self, req: UpdateGenerationResultReq
    ) -> UpdateGenerationResultRes:
        updates = req.updates.model_dump(exclude_unset=True)
        self.generation_results.update(req.id, updates)
        return UpdateGenerationResultRes()

    async def async_delete_generation_result(
        self, req: DeleteGenerationResultReq
    ) -> DeleteGenerationResultRes:
        self.generation_results.delete(req.id)
        return DeleteGenerationResultRes()

    # TaskDefinition methods
    async def async_create_task_definition(
        self, req: CreateTaskDefinitionReq
    ) -> CreateTaskDefinitionRes:
        id = self._generate_id()
        data = req.properties.model_dump()
        data["id"] = id
        self.task_definitions.create(id, data)
        return CreateTaskDefinitionRes(id=id)

    async def async_get_task_definition(
        self, req: GetTaskDefinitionReq
    ) -> GetTaskDefinitionRes:
        data = self.task_definitions.get(req.id)
        if data is None:
            raise ValueError(f"TaskDefinition {req.id} not found")
        return GetTaskDefinitionRes(TaskDefinition=TaskDefinition(**data))

    async def async_update_task_definition(
        self, req: UpdateTaskDefinitionReq
    ) -> UpdateTaskDefinitionRes:
        updates = req.updates.model_dump(exclude_unset=True)
        self.task_definitions.update(req.id, updates)
        return UpdateTaskDefinitionRes()

    async def async_delete_task_definition(
        self, req: DeleteTaskDefinitionReq
    ) -> DeleteTaskDefinitionRes:
        self.task_definitions.delete(req.id)
        return DeleteTaskDefinitionRes()

    # TaskExample methods
    async def async_create_task_example(
        self, req: CreateTaskExampleReq
    ) -> CreateTaskExampleRes:
        # Verify references exist
        if not self.task_definitions.exists(req.properties.task_definition_id):
            raise ValueError(
                f"TaskDefinition {req.properties.task_definition_id} not found"
            )
        if not self.input_payloads.exists(req.properties.input_payload_id):
            raise ValueError(
                f"InputPayload {req.properties.input_payload_id} not found"
            )

        id = self._generate_id()
        data = req.properties.model_dump()
        data["id"] = id
        self.task_examples.create(id, data)
        return CreateTaskExampleRes(id=id)

    async def async_get_task_example(self, req: GetTaskExampleReq) -> GetTaskExampleRes:
        data = self.task_examples.get(req.id)
        if data is None:
            raise ValueError(f"TaskExample {req.id} not found")
        return GetTaskExampleRes(TaskExample=TaskExample(**data))

    async def async_update_task_example(
        self, req: UpdateTaskExampleReq
    ) -> UpdateTaskExampleRes:
        updates = req.updates.model_dump(exclude_unset=True)
        self.task_examples.update(req.id, updates)
        return UpdateTaskExampleRes()

    async def async_delete_task_example(
        self, req: DeleteTaskExampleReq
    ) -> DeleteTaskExampleRes:
        self.task_examples.delete(req.id)
        return DeleteTaskExampleRes()

    # ScorerClass methods
    async def async_create_scorer_class(
        self, req: CreateScorerClassReq
    ) -> CreateScorerClassRes:
        id = self._generate_id()
        data = req.properties.model_dump()
        data["id"] = id
        self.scorer_classes.create(id, data)
        return CreateScorerClassRes(id=id)

    async def async_get_scorer_class(self, req: GetScorerClassReq) -> GetScorerClassRes:
        data = self.scorer_classes.get(req.id)
        if data is None:
            raise ValueError(f"ScorerClass {req.id} not found")
        return GetScorerClassRes(ScorerClass=ScorerClass(**data))

    async def async_update_scorer_class(
        self, req: UpdateScorerClassReq
    ) -> UpdateScorerClassRes:
        updates = req.updates.model_dump(exclude_unset=True)
        self.scorer_classes.update(req.id, updates)
        return UpdateScorerClassRes()

    async def async_delete_scorer_class(
        self, req: DeleteScorerClassReq
    ) -> DeleteScorerClassRes:
        self.scorer_classes.delete(req.id)
        return DeleteScorerClassRes()

    # ScorerInstance methods
    async def async_create_scorer_instance(
        self, req: CreateScorerInstanceReq
    ) -> CreateScorerInstanceRes:
        # Verify scorer class exists
        if not self.scorer_classes.exists(req.properties.scorer_class_id):
            raise ValueError(f"ScorerClass {req.properties.scorer_class_id} not found")

        id = self._generate_id()
        data = req.properties.model_dump()
        data["id"] = id
        self.scorer_instances.create(id, data)
        return CreateScorerInstanceRes(id=id)

    async def async_get_scorer_instance(
        self, req: GetScorerInstanceReq
    ) -> GetScorerInstanceRes:
        data = self.scorer_instances.get(req.id)
        if data is None:
            raise ValueError(f"ScorerInstance {req.id} not found")
        return GetScorerInstanceRes(ScorerInstance=ScorerInstance(**data))

    async def async_update_scorer_instance(
        self, req: UpdateScorerInstanceReq
    ) -> UpdateScorerInstanceRes:
        updates = req.updates.model_dump(exclude_unset=True)
        self.scorer_instances.update(req.id, updates)
        return UpdateScorerInstanceRes()

    async def async_delete_scorer_instance(
        self, req: DeleteScorerInstanceReq
    ) -> DeleteScorerInstanceRes:
        self.scorer_instances.delete(req.id)
        return DeleteScorerInstanceRes()

    # ScoreResult methods
    async def async_create_score_result(
        self, req: CreateScoreResultReq
    ) -> CreateScoreResultRes:
        # Verify references exist
        if not self.scorer_instances.exists(req.properties.scorer_instance_id):
            raise ValueError(
                f"ScorerInstance {req.properties.scorer_instance_id} not found"
            )
        if not self.generation_results.exists(req.properties.generation_result_id):
            raise ValueError(
                f"GenerationResult {req.properties.generation_result_id} not found"
            )
        if not self.example_labels.exists(req.properties.example_label_id):
            raise ValueError(
                f"ExampleLabel {req.properties.example_label_id} not found"
            )
        if not self.input_payloads.exists(req.properties.input_payload_id):
            raise ValueError(
                f"InputPayload {req.properties.input_payload_id} not found"
            )

        id = self._generate_id()
        data = req.properties.model_dump()
        data["id"] = id
        self.score_results.create(id, data)
        return CreateScoreResultRes(id=id)

    async def async_get_score_result(self, req: GetScoreResultReq) -> GetScoreResultRes:
        data = self.score_results.get(req.id)
        if data is None:
            raise ValueError(f"ScoreResult {req.id} not found")
        return GetScoreResultRes(ScoreResult=ScoreResult(**data))

    async def async_update_score_result(
        self, req: UpdateScoreResultReq
    ) -> UpdateScoreResultRes:
        updates = req.updates.model_dump(exclude_unset=True)
        self.score_results.update(req.id, updates)
        return UpdateScoreResultRes()

    async def async_delete_score_result(
        self, req: DeleteScoreResultReq
    ) -> DeleteScoreResultRes:
        self.score_results.delete(req.id)
        return DeleteScoreResultRes()

    # ExampleLabel methods
    async def async_create_example_label(
        self, req: CreateExampleLabelReq
    ) -> CreateExampleLabelRes:
        # Verify task example exists
        if not self.task_examples.exists(req.properties.task_example_id):
            raise ValueError(f"TaskExample {req.properties.task_example_id} not found")

        id = self._generate_id()
        data = req.properties.model_dump()
        data["id"] = id
        self.example_labels.create(id, data)
        return CreateExampleLabelRes(id=id)

    async def async_get_example_label(
        self, req: GetExampleLabelReq
    ) -> GetExampleLabelRes:
        data = self.example_labels.get(req.id)
        if data is None:
            raise ValueError(f"ExampleLabel {req.id} not found")
        return GetExampleLabelRes(ExampleLabel=ExampleLabel(**data))

    async def async_update_example_label(
        self, req: UpdateExampleLabelReq
    ) -> UpdateExampleLabelRes:
        updates = req.updates.model_dump(exclude_unset=True)
        self.example_labels.update(req.id, updates)
        return UpdateExampleLabelRes()

    async def async_delete_example_label(
        self, req: DeleteExampleLabelReq
    ) -> DeleteExampleLabelRes:
        self.example_labels.delete(req.id)
        return DeleteExampleLabelRes()

    # EvaluationSummary methods
    async def async_create_evaluation_summary(
        self, req: CreateEvaluationSummaryReq
    ) -> CreateEvaluationSummaryRes:
        # Verify references exist
        if not self.model_instances.exists(req.properties.model_instance_id):
            raise ValueError(
                f"ModelInstance {req.properties.model_instance_id} not found"
            )
        if not self.task_definitions.exists(req.properties.task_definition_id):
            raise ValueError(
                f"TaskDefinition {req.properties.task_definition_id} not found"
            )
        if not self.scorer_instances.exists(req.properties.scorer_instance_id):
            raise ValueError(
                f"ScorerInstance {req.properties.scorer_instance_id} not found"
            )

        # Verify all referenced examples, labels, and scores exist
        for task_example_id in req.properties.task_example_ids:
            if not self.task_examples.exists(task_example_id):
                raise ValueError(f"TaskExample {task_example_id} not found")

        for example_label_id in req.properties.example_label_ids:
            if not self.example_labels.exists(example_label_id):
                raise ValueError(f"ExampleLabel {example_label_id} not found")

        for score_result_id in req.properties.score_result_ids:
            if not self.score_results.exists(score_result_id):
                raise ValueError(f"ScoreResult {score_result_id} not found")

        id = self._generate_id()
        data = req.properties.model_dump()
        data["id"] = id
        self.evaluation_summaries.create(id, data)
        return CreateEvaluationSummaryRes(id=id)

    async def async_get_evaluation_summary(
        self, req: GetEvaluationSummaryReq
    ) -> GetEvaluationSummaryRes:
        data = self.evaluation_summaries.get(req.id)
        if data is None:
            raise ValueError(f"EvaluationSummary {req.id} not found")
        return GetEvaluationSummaryRes(EvaluationSummary=EvaluationSummary(**data))

    async def async_update_evaluation_summary(
        self, req: UpdateEvaluationSummaryReq
    ) -> UpdateEvaluationSummaryRes:
        updates = req.updates.model_dump(exclude_unset=True)
        self.evaluation_summaries.update(req.id, updates)
        return UpdateEvaluationSummaryRes()

    async def async_delete_evaluation_summary(
        self, req: DeleteEvaluationSummaryReq
    ) -> DeleteEvaluationSummaryRes:
        self.evaluation_summaries.delete(req.id)
        return DeleteEvaluationSummaryRes()
