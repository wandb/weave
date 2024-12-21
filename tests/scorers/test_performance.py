"""Tests for scorer performance requirements (latency, memory, CPU)."""
import time
import psutil
import os
import pytest
from weave.scorers import (
    BLEUScorer,
    RougeScorer,
    CoherenceScorer,
    ContextRelevanceScorer,
    RobustnessScorer,
)
from tests.scorers.test_utils import generate_large_text, generate_context_and_output


def format_metrics(metrics):
    """Format performance metrics for display."""
    return (
        f"latency={metrics.latency:.2f}s, "
        f"memory={metrics.memory_used:.1f}MB, "
        f"peak_mem={metrics.memory_peak:.1f}MB, "
        f"cpu={metrics.cpu_percent:.1f}%"
    )


@pytest.mark.asyncio
async def test_scorer_performance(
    mock_wandb,
    mock_model_loading,
    mock_pipeline_factory,
    measure_performance,
    test_cases,
    monkeypatch
):
    """Test that all scorers meet performance requirements."""
    # Configure scorers
    scorers = {
        "bleu": BLEUScorer(),
        "rouge": RougeScorer(),
        "coherence": CoherenceScorer(
            model_name_or_path="wandb/coherence_scorer",
            device="cpu",
            name="test-coherence",
        ),
        "context_relevance": ContextRelevanceScorer(
            model_name_or_path="wandb/relevance_scorer",
            device="cpu",
            name="test-relevance",
        ),
        "robustness": RobustnessScorer(),
    }

    # Mock model-based scorers
    for scorer_name in ["coherence", "context_relevance"]:
        scorer = scorers[scorer_name]
        mock_pipeline = mock_pipeline_factory(scorer_name)
        monkeypatch.setattr("transformers.pipeline", mock_pipeline)
        monkeypatch.setattr(scorer, "_classifier", mock_pipeline())

    # Test cases with different input sizes
    for case_name, case_data in test_cases.items():
        if isinstance(case_data, dict) and "input" in case_data:  # Skip edge_cases dict
            print(f"\nTesting {case_name} inputs:")
            
            for scorer_name, scorer in scorers.items():
                print(f"  {scorer_name}:", end=" ", flush=True)
                
                try:
                    if scorer_name in ["bleu", "rouge"]:
                        # Test with ground truth-based scorers
                        _, metrics = measure_performance(
                            scorer.score,
                            ground_truths=[case_data["output"]],
                            output=case_data["output"]
                        )
                    elif scorer_name == "robustness":
                        # Test robustness scorer
                        _, metrics = measure_performance(
                            scorer.score,
                            input=case_data["input"],
                            output=case_data["output"]
                        )
                    elif scorer_name == "context_relevance":
                        # Test context relevance scorer
                        _, metrics = await measure_performance(
                            scorer.score,
                            input=case_data["input"],
                            output=case_data["output"],
                            context=case_data["context"]
                        )
                    else:
                        # Test other scorers
                        _, metrics = await measure_performance(
                            scorer.score,
                            input=case_data["input"],
                            output=case_data["output"]
                        )
                    
                    print(format_metrics(metrics))
                
                except Exception as e:
                    print(f"ERROR: {str(e)}")
                    raise


@pytest.mark.asyncio
async def test_scorer_performance_large_inputs(
    mock_wandb,
    mock_model_loading,
    mock_pipeline_factory,
    measure_performance,
    monkeypatch
):
    """Test scorer performance with very large inputs."""
    # Generate large inputs
    large_input = generate_large_text(tokens=50000)
    large_context, large_output = generate_context_and_output(
        total_tokens=100000,
        context_ratio=0.7
    )

    # Configure scorers
    scorers = {
        "bleu": BLEUScorer(),
        "rouge": RougeScorer(),
        "coherence": CoherenceScorer(
            model_name_or_path="wandb/coherence_scorer",
            device="cpu",
            name="test-coherence",
        ),
        "context_relevance": ContextRelevanceScorer(
            model_name_or_path="wandb/relevance_scorer",
            device="cpu",
            name="test-relevance",
        ),
        "robustness": RobustnessScorer(),
    }

    # Mock model-based scorers
    for scorer_name in ["coherence", "context_relevance"]:
        scorer = scorers[scorer_name]
        mock_pipeline = mock_pipeline_factory(scorer_name)
        monkeypatch.setattr("transformers.pipeline", mock_pipeline)
        monkeypatch.setattr(scorer, "_classifier", mock_pipeline())

    print("\nTesting with large inputs:")
    for scorer_name, scorer in scorers.items():
        print(f"  {scorer_name}:", end=" ", flush=True)
        
        try:
            if scorer_name in ["bleu", "rouge"]:
                # Test with ground truth-based scorers
                _, metrics = measure_performance(
                    scorer.score,
                    ground_truths=[large_output],
                    output=large_output,
                    memory_threshold_mb=2048.0  # Allow up to 2GB for large inputs
                )
            elif scorer_name == "robustness":
                # Test robustness scorer
                _, metrics = measure_performance(
                    scorer.score,
                    input=large_input,
                    output=large_output,
                    memory_threshold_mb=2048.0
                )
            elif scorer_name == "context_relevance":
                # Test context relevance scorer
                _, metrics = await measure_performance(
                    scorer.score,
                    input=large_input,
                    output=large_output,
                    context=large_context,
                    memory_threshold_mb=2048.0
                )
            else:
                # Test other scorers
                _, metrics = await measure_performance(
                    scorer.score,
                    input=large_input,
                    output=large_output,
                    memory_threshold_mb=2048.0
                )
            
            print(format_metrics(metrics))
        
        except Exception as e:
            print(f"ERROR: {str(e)}")
            raise


@pytest.mark.asyncio
async def test_scorer_performance_concurrent(
    mock_wandb,
    mock_model_loading,
    mock_pipeline_factory,
    measure_performance,
    test_cases,
    monkeypatch
):
    """Test scorer performance when running multiple scoring operations concurrently."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    # Configure scorers
    scorers = {
        "bleu": BLEUScorer(),
        "rouge": RougeScorer(),
        "coherence": CoherenceScorer(
            model_name_or_path="wandb/coherence_scorer",
            device="cpu",
            name="test-coherence",
        ),
        "context_relevance": ContextRelevanceScorer(
            model_name_or_path="wandb/relevance_scorer",
            device="cpu",
            name="test-relevance",
        ),
        "robustness": RobustnessScorer(),
    }

    # Mock model-based scorers
    for scorer_name in ["coherence", "context_relevance"]:
        scorer = scorers[scorer_name]
        mock_pipeline = mock_pipeline_factory(scorer_name)
        monkeypatch.setattr("transformers.pipeline", mock_pipeline)
        monkeypatch.setattr(scorer, "_classifier", mock_pipeline())

    case_data = test_cases["medium"]  # Use medium-sized inputs for concurrent testing
    
    async def run_concurrent_scores():
        tasks = []
        for scorer_name, scorer in scorers.items():
            if scorer_name in ["bleu", "rouge"]:
                # Ground truth-based scorers
                tasks.append(
                    asyncio.get_event_loop().run_in_executor(
                        ThreadPoolExecutor(),
                        scorer.score,
                        [case_data["output"]],
                        case_data["output"]
                    )
                )
            elif scorer_name == "robustness":
                # Robustness scorer
                tasks.append(
                    asyncio.get_event_loop().run_in_executor(
                        ThreadPoolExecutor(),
                        scorer.score,
                        case_data["input"],
                        case_data["output"]
                    )
                )
            elif scorer_name == "context_relevance":
                # Context relevance scorer
                tasks.append(
                    scorer.score(
                        input=case_data["input"],
                        output=case_data["output"],
                        context=case_data["context"]
                    )
                )
            else:
                # Other scorers
                tasks.append(
                    scorer.score(
                        input=case_data["input"],
                        output=case_data["output"]
                    )
                )
        
        results = await asyncio.gather(*tasks)
        return results

    print("\nTesting concurrent scoring:")
    results, metrics = await measure_performance(
        run_concurrent_scores,
        latency_threshold=60.0,  # Allow extra time for concurrent operations
        memory_threshold_mb=4096.0  # Allow up to 4GB for concurrent operations
    )
    
    print(f"Concurrent performance: {format_metrics(metrics)}")
    assert len(results) == len(scorers), "Not all scorers returned results"


@pytest.mark.asyncio
async def test_scorer_performance_edge_cases(
    mock_wandb,
    mock_model_loading,
    mock_pipeline_factory,
    measure_performance,
    test_cases,
    monkeypatch
):
    """Test scorer performance with edge cases."""
    # Configure scorers
    scorers = {
        "bleu": BLEUScorer(),
        "rouge": RougeScorer(),
        "coherence": CoherenceScorer(
            model_name_or_path="wandb/coherence_scorer",
            device="cpu",
            name="test-coherence",
        ),
        "context_relevance": ContextRelevanceScorer(
            model_name_or_path="wandb/relevance_scorer",
            device="cpu",
            name="test-relevance",
        ),
        "robustness": RobustnessScorer(),
    }

    # Mock model-based scorers
    for scorer_name in ["coherence", "context_relevance"]:
        scorer = scorers[scorer_name]
        mock_pipeline = mock_pipeline_factory(scorer_name)
        monkeypatch.setattr("transformers.pipeline", mock_pipeline)
        monkeypatch.setattr(scorer, "_classifier", mock_pipeline())

    edge_cases = test_cases["edge_cases"]
    for case_name, case_data in edge_cases.items():
        print(f"\nTesting {case_name} edge case:")
        
        for scorer_name, scorer in scorers.items():
            print(f"  {scorer_name}:", end=" ", flush=True)
            
            try:
                if scorer_name in ["bleu", "rouge"]:
                    # Test with ground truth-based scorers
                    _, metrics = measure_performance(
                        scorer.score,
                        ground_truths=[case_data["output"]],
                        output=case_data["output"]
                    )
                elif scorer_name == "robustness":
                    # Test robustness scorer
                    _, metrics = measure_performance(
                        scorer.score,
                        input=case_data["input"],
                        output=case_data["output"]
                    )
                elif scorer_name == "context_relevance":
                    # Test context relevance scorer
                    _, metrics = await measure_performance(
                        scorer.score,
                        input=case_data["input"],
                        output=case_data["output"],
                        context=case_data["context"]
                    )
                else:
                    # Test other scorers
                    _, metrics = await measure_performance(
                        scorer.score,
                        input=case_data["input"],
                        output=case_data["output"]
                    )
                
                print(format_metrics(metrics))
            
            except Exception as e:
                print(f"ERROR: {str(e)}")
                # For edge cases, we log errors but don't raise them
                print(f"        Error with {scorer_name} on {case_name}: {str(e)}")