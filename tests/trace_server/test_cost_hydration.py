import datetime

import pytest

from weave.trace_server.cost_hydration import (
    PriceRow,
    build_price_indexes,
    hydrate_calls_with_costs,
)


def _price_row(
    llm_id: str,
    pricing_level: str,
    pricing_level_id: str,
    effective_date: datetime.datetime,
    prompt_cost: float,
) -> PriceRow:
    return {
        "id": f"{llm_id}-{pricing_level}-{effective_date.isoformat()}",
        "pricing_level": pricing_level,
        "pricing_level_id": pricing_level_id,
        "provider_id": "test-provider",
        "llm_id": llm_id,
        "effective_date": effective_date,
        "prompt_token_cost": prompt_cost,
        "completion_token_cost": prompt_cost * 2,
        "cache_read_input_token_cost": prompt_cost / 10,
        "cache_creation_input_token_cost": prompt_cost / 5,
        "prompt_token_cost_unit": "USD",
        "completion_token_cost_unit": "USD",
        "created_by": "tester",
        "created_at": effective_date,
    }


def test_hydrate_calls_with_costs_normalizes_usage_and_matches_sql_ranking() -> None:
    project_id = "project-1"
    started_at = datetime.datetime(2026, 5, 4, 14, tzinfo=datetime.timezone.utc)
    price_indexes = build_price_indexes(
        [
            _price_row(
                "model-a",
                "default",
                "default",
                started_at - datetime.timedelta(minutes=1),
                0.02,
            ),
            _price_row(
                "model-a",
                "project",
                project_id,
                started_at - datetime.timedelta(days=1),
                0.01,
            ),
            _price_row(
                "model-a",
                "project",
                project_id,
                started_at + datetime.timedelta(days=1),
                0.99,
            ),
            _price_row(
                "model-b",
                "project",
                project_id,
                started_at + datetime.timedelta(days=1),
                0.03,
            ),
            _price_row(
                "model-b",
                "project",
                project_id,
                started_at + datetime.timedelta(days=2),
                0.04,
            ),
        ],
        project_id,
    )
    calls = [
        {
            "id": "call-1",
            "started_at": started_at,
            "summary": {
                "usage": {
                    "model-a": {
                        "prompt_tokens": 10,
                        "input_tokens": 5,
                        "completion_tokens": 7,
                        "output_tokens": 3,
                        "cache_read_input_tokens": 2,
                        "cache_creation_input_tokens": 1,
                        "requests": 1,
                        "total_tokens": 30,
                    },
                    "model-missing-price": {
                        "prompt_tokens": 1,
                        "completion_tokens": 1,
                    },
                },
                "weave": {"costs": {"stale": {}}},
            },
        },
        {
            "id": "call-2",
            "started_at": started_at,
            "summary": {
                "usage": {
                    "model-b": {
                        "prompt_tokens": 10,
                        "completion_tokens": 10,
                    }
                }
            },
        },
    ]

    hydrate_calls_with_costs(calls, price_indexes)

    costs_a = calls[0]["summary"]["weave"]["costs"]["model-a"]
    assert set(calls[0]["summary"]["weave"]["costs"]) == {"model-a"}
    assert costs_a["prompt_tokens"] == 15
    assert costs_a["completion_tokens"] == 10
    assert costs_a["prompt_token_cost"] == pytest.approx(0.01)
    assert costs_a["completion_token_cost"] == pytest.approx(0.02)
    assert costs_a["prompt_tokens_total_cost"] == pytest.approx((15 - 2 - 1) * 0.01)
    assert costs_a["completion_tokens_total_cost"] == pytest.approx(10 * 0.02)
    assert costs_a["cache_read_input_tokens_total_cost"] == pytest.approx(2 * 0.001)
    assert costs_a["cache_creation_input_tokens_total_cost"] == pytest.approx(1 * 0.002)
    assert costs_a["pricing_level"] == "project"
    assert costs_a["pricing_level_id"] == project_id

    # If all prices are future-dated, match the existing SQL ordering and pick
    # the latest future row within the best pricing level.
    costs_b = calls[1]["summary"]["weave"]["costs"]["model-b"]
    assert costs_b["prompt_token_cost"] == pytest.approx(0.04)
