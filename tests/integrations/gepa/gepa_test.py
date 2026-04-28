from __future__ import annotations

from collections.abc import Generator
from typing import Any

import gepa
import gepa.optimize_anything as oa
import pytest
from gepa.core.adapter import EvaluationBatch
from gepa.optimize_anything import EngineConfig, GEPAConfig, ReflectionConfig

from weave.integrations.gepa import gepa_sdk
from weave.integrations.gepa.gepa_sdk import get_gepa_patcher
from weave.integrations.integration_utilities import op_name_from_ref
from weave.trace.weave_client import WeaveClient


def _optimize_anything_candidate_proposer(
    candidate: dict[str, str],
    reflective_dataset: dict[str, list[dict[str, Any]]],
    components_to_update: list[str],
) -> dict[str, str]:
    del candidate, reflective_dataset
    return {
        component: "optimized prompt" if component == "current_candidate" else ""
        for component in components_to_update
    }


def _gepa_candidate_proposer(
    candidate: dict[str, str],
    reflective_dataset: dict[str, list[dict[str, Any]]],
    components_to_update: list[str],
) -> dict[str, str]:
    del candidate, reflective_dataset
    return {
        component: "correct answer" if component == "prompt" else ""
        for component in components_to_update
    }


class SimpleGEPAAdapter:
    propose_new_texts = None

    def evaluate(
        self,
        batch: list[str],
        candidate: dict[str, str],
        capture_traces: bool = False,
    ) -> EvaluationBatch[dict[str, str], str]:
        outputs: list[str] = []
        scores: list[float] = []
        trajectories: list[dict[str, str]] = []

        for example in batch:
            output = candidate["prompt"]
            outputs.append(output)
            scores.append(1.0 if output == example else 0.0)
            trajectories.append({"example": example, "output": output})

        return EvaluationBatch(
            outputs=outputs,
            scores=scores,
            trajectories=trajectories if capture_traces else None,
        )

    def make_reflective_dataset(
        self,
        candidate: dict[str, str],
        eval_batch: EvaluationBatch[dict[str, str], str],
        components_to_update: list[str],
    ) -> dict[str, list[dict[str, Any]]]:
        del candidate
        records = [
            {
                "Input": trajectory["example"],
                "Generated Output": trajectory["output"],
                "Feedback": f"score={score}",
            }
            for trajectory, score in zip(
                eval_batch.trajectories or [],
                eval_batch.scores,
                strict=False,
            )
        ]
        reflective_dataset: dict[str, list[dict[str, Any]]] = {}
        for component in components_to_update:
            reflective_dataset[component] = list(records)
        return reflective_dataset


@pytest.fixture(autouse=True)
def patch_gepa() -> Generator[None, None, None]:
    gepa_sdk._gepa_patcher = None
    patcher = get_gepa_patcher()
    patcher.attempt_patch()

    yield

    patcher.undo_patch()
    gepa_sdk._gepa_patcher = None


@pytest.mark.skip_clickhouse_client
def test_gepa_optimize_anything_traced(client: WeaveClient) -> None:
    def evaluator(candidate: str) -> tuple[float, dict[str, Any]]:
        oa.log(f"candidate={candidate}")
        return (
            1.0 if candidate == "optimized prompt" else 0.0,
            {"candidate": candidate},
        )

    config = GEPAConfig(
        engine=EngineConfig(max_metric_calls=2, parallel=False, max_workers=1),
        reflection=ReflectionConfig(
            reflection_lm=None,
            custom_candidate_proposer=_optimize_anything_candidate_proposer,
        ),
    )

    result = oa.optimize_anything(
        seed_candidate="initial prompt",
        evaluator=evaluator,
        config=config,
    )

    assert result.best_candidate == "optimized prompt"

    calls = list(client.get_calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "gepa.optimize_anything"


@pytest.mark.skip_clickhouse_client
def test_gepa_optimize_traced(client: WeaveClient) -> None:
    result = gepa.optimize(
        seed_candidate={"prompt": "wrong answer"},
        trainset=["correct answer"],
        adapter=SimpleGEPAAdapter(),
        custom_candidate_proposer=_gepa_candidate_proposer,
        max_metric_calls=2,
    )

    assert result.best_candidate["prompt"] == "correct answer"

    calls = list(client.get_calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "gepa.optimize"
