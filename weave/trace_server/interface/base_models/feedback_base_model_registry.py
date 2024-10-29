from typing import Any, Optional

from pydantic import BaseModel

from weave.trace_server import refs_internal as ri


class MachineScore(BaseModel):
    runnable_ref: str
    """
    Reference to the "runnable" that generated this score.
    A "runnable" is something that can be executed:
    - An `Op`
    - A `Scorer` instance (weave object with `score` method and optional `summarize` method)
    - A `Model` instance (weave object with `predict` method)
    - (Future) A `Function` instance (weave object with `call` method)
    - (Future) A "BoundOp" - this is an object that partially binds an `Op`
    - A `ConfiguredAction` - the new Weave Object that defines an Action (eg. configured LLM Judge).
        - IMPORTANT: ConfiguredActions in themselves have different types, one of which will inevitably be "ExecuteOp".
                     In the case of "ExecuteOp", if there are no other configuration in the `ConfiguredAction`, then
                     we should store the `Op`'s reference instead. This will allow us to have a uniform feedback schema
                     for Scorers, regardless of if they are executed by user or by the backend system.
    """
    call_ref: Optional[str]
    """
    Reference to the call that generated this score. Not all runnables generate a call, but when they do, we want to store the reference.
    """
    trigger_ref: Optional[str]
    """
    Reference to the trigger that generated this score. Not all MachineScores are triggered (some are manual), but when they are, we want to store the reference.
    """
    value: dict[str, dict[str, Any]]
    """
    The result of the runnable, nested by the runnable's object id and digest.
    """

    def model_post_init(self, __context: Any) -> None:
        # Validate runnable_ref is a valid ref
        parsed_runnable_ref = ri.parse_internal_uri(self.runnable_ref)
        if not isinstance(
            parsed_runnable_ref, (ri.InternalObjectRef, ri.InternalOpRef)
        ):
            raise ValueError(f"Invalid runnable_ref: {self.runnable_ref}")

        # Validate call_ref is a valid ref if it exists
        if self.call_ref:
            parsed_call_ref = ri.parse_internal_uri(self.call_ref)
            if not isinstance(parsed_call_ref, ri.InternalCallRef):
                raise ValueError(f"Invalid call_ref: {self.call_ref}")

        # Validate trigger_ref is a valid ref if it exists
        if self.trigger_ref:
            parsed_trigger_ref = ri.parse_internal_uri(self.trigger_ref)
            if not isinstance(parsed_trigger_ref, ri.InternalObjectRef):
                raise ValueError(f"Invalid trigger_ref: {self.trigger_ref}")

        # Validate value is a dict of dicts with the correct keys
        expected_name = parsed_runnable_ref.name
        expected_digest = parsed_runnable_ref.version
        name_keys = list(self.value.keys())
        if name_keys != [expected_name]:
            raise ValueError(f"Invalid value: {self.value}. Expected: {expected_name}")

        digest_keys = list(self.value[expected_name].keys())
        if digest_keys != [expected_digest]:
            raise ValueError(
                f"Invalid value: {self.value}. Expected: {expected_digest}"
            )


feedback_base_models: list[type[BaseModel]] = [MachineScore]
