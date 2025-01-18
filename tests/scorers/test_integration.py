"""Integration tests for scorers combining multiple scorers and real model usage."""
import pytest
import weave
from weave.scorers import (
    BLEUScorer,
    RougeScorer,
    CoherenceScorer,
    ContextRelevanceScorer,
    RobustnessScorer,
    ToxicScorer,
    GenderRaceBiasScorer,
)
from weave import Evaluation


@pytest.fixture
def real_model_scorers():
    """Initialize scorers that use ML models with real model weights."""
    return {
        "coherence": CoherenceScorer(
            model_name_or_path="wandb/coherence_scorer",
            device="cpu",
            name="test-coherence",
        ),
        "toxic": ToxicScorer(
            model_name_or_path="wandb/toxic_scorer",
            device="cpu",
            name="test-toxic",
        ),
        "bias": GenderRaceBiasScorer(
            model_name_or_path="wandb/bias_scorer",
            device="cpu",
            name="test-bias",
        ),
    }


@pytest.fixture
def metric_scorers():
    """Initialize metric-based scorers."""
    return {
        "bleu": BLEUScorer(),
        "rouge": RougeScorer(),
        "robustness": RobustnessScorer(),
    }


@pytest.mark.asyncio
async def test_full_evaluation_pipeline(real_model_scorers, metric_scorers):
    """Test a full evaluation pipeline using all scorers together."""
    # Create a test dataset
    dataset = [
        {
            "input": "What is artificial intelligence?",
            "output": "Artificial intelligence is the simulation of human intelligence by machines.",
            "context": "AI is a broad field of computer science focused on creating intelligent machines.",
            "ground_truth": "Artificial intelligence refers to systems that can simulate human intelligence.",
        },
        {
            "input": "Explain quantum computing.",
            "output": "Quantum computing uses quantum mechanics principles for computation.",
            "context": "Quantum computers leverage quantum mechanical phenomena like superposition.",
            "ground_truth": "Quantum computing is a type of computation that uses quantum mechanical phenomena.",
        },
    ]

    # Simple test model
    @weave.op
    def test_model(input: str):
        return "This is a test response about " + input.lower().split()[1]

    # Combine all scorers
    all_scorers = [*real_model_scorers.values(), *metric_scorers.values()]

    # Create evaluation
    evaluation = Evaluation(
        dataset=dataset,
        scorers=all_scorers,
    )

    # Run evaluation
    results = await evaluation.evaluate(test_model)

    # Verify results from each scorer
    for scorer in real_model_scorers:
        assert scorer in results, f"Missing results for {scorer}"
        
    for scorer in metric_scorers:
        assert scorer in results, f"Missing results for {scorer}"


@pytest.mark.asyncio
async def test_model_chain_evaluation(real_model_scorers):
    """Test evaluation of a chain of models with intermediate outputs."""
    
    # Define a simple chain of models
    @weave.op
    def preprocessor(input: str):
        return f"Processed: {input}"

    @weave.op
    def main_model(processed_input: str):
        return f"Response to {processed_input}"

    @weave.op
    def postprocessor(model_output: str):
        return f"Final: {model_output}"

    # Create test dataset
    dataset = [
        {
            "input": "Test query 1",
            "context": "Context for query 1",
        },
        {
            "input": "Test query 2",
            "context": "Context for query 2",
        },
    ]

    # Create evaluation for each step
    preprocessor_eval = Evaluation(
        dataset=dataset,
        scorers=[real_model_scorers["coherence"]],
    )
    
    main_model_eval = Evaluation(
        dataset=dataset,
        scorers=[
            real_model_scorers["coherence"],
            real_model_scorers["toxic"],
            real_model_scorers["bias"],
        ],
    )
    
    postprocessor_eval = Evaluation(
        dataset=dataset,
        scorers=[real_model_scorers["coherence"]],
    )

    # Run evaluations
    preprocess_results = await preprocessor_eval.evaluate(preprocessor)
    model_results = await main_model_eval.evaluate(main_model)
    postprocess_results = await postprocessor_eval.evaluate(postprocessor)

    # Verify results
    assert "coherence" in preprocess_results
    assert all(scorer in model_results for scorer in ["coherence", "toxic", "bias"])
    assert "coherence" in postprocess_results


@pytest.mark.asyncio
async def test_cross_scorer_validation(real_model_scorers, metric_scorers):
    """Test that different scorers' results are consistent with each other."""
    
    test_text = "This is a high quality, unbiased, and coherent response."
    
    # Get scores from all scorers
    scores = {}
    
    # Test ML model scorers
    for name, scorer in real_model_scorers.items():
        result = await scorer.score(
            input="Test prompt",
            output=test_text
        )
        scores[name] = result

    # Test metric scorers
    for name, scorer in metric_scorers.items():
        if name in ["bleu", "rouge"]:
            result = scorer.score(
                ground_truths=[test_text],
                output=test_text
            )
        else:
            result = scorer.score(
                input="Test prompt",
                output=test_text
            )
        scores[name] = result

    # Verify score consistency
    # High coherence should correlate with low toxicity
    assert scores["coherence"]["coherent"] == True
    assert scores["toxic"]["flagged"] == False

    # Perfect BLEU score for identical text
    assert scores["bleu"]["sentence_bleu"] == 100.0


@pytest.mark.asyncio
async def test_error_propagation(real_model_scorers, metric_scorers):
    """Test how errors in one scorer affect the overall evaluation."""
    
    # Create a dataset with some problematic inputs
    dataset = [
        {
            "input": "Normal input",
            "output": "Normal output",
            "context": "Normal context",
        },
        {
            "input": "",  # Empty input
            "output": "Some output",
            "context": "Some context",
        },
        {
            "input": "Input with very " + "long " * 1000 + "text",  # Very long input
            "output": "Output",
            "context": "Context",
        },
    ]

    # Create evaluation with all scorers
    all_scorers = [*real_model_scorers.values(), *metric_scorers.values()]
    
    @weave.op
    def test_model(input: str):
        return f"Response to: {input}"

    evaluation = Evaluation(
        dataset=dataset,
        scorers=all_scorers,
    )

    # Run evaluation and verify error handling
    try:
        results = await evaluation.evaluate(test_model)
        
        # Check that results contain error information
        for scorer_name in [*real_model_scorers.keys(), *metric_scorers.keys()]:
            assert scorer_name in results, f"Missing results for {scorer_name}"
            
            # Check error handling for empty input
            assert "error_count" in results[scorer_name], f"Missing error count for {scorer_name}"
            
    except Exception as e:
        pytest.fail(f"Evaluation failed to handle errors gracefully: {str(e)}")


@pytest.mark.asyncio
async def test_large_scale_evaluation(real_model_scorers, metric_scorers):
    """Test evaluation with a larger dataset to verify scalability."""
    
    # Create a larger dataset
    dataset = [
        {
            "input": f"Query {i}",
            "output": f"Response {i}",
            "context": f"Context {i}",
        }
        for i in range(100)  # Test with 100 examples
    ]

    # Create evaluation with all scorers
    all_scorers = [*real_model_scorers.values(), *metric_scorers.values()]
    
    @weave.op
    def test_model(input: str):
        return f"Response to: {input}"

    evaluation = Evaluation(
        dataset=dataset,
        scorers=all_scorers,
    )

    # Run evaluation with performance monitoring
    start_time = time.time()
    results = await evaluation.evaluate(test_model)
    total_time = time.time() - start_time

    # Verify scalability
    print(f"\nLarge-scale evaluation completed in {total_time:.2f} seconds")
    print(f"Average time per example: {total_time/len(dataset):.2f} seconds")

    # Verify all results are present
    for scorer_name in [*real_model_scorers.keys(), *metric_scorers.keys()]:
        assert scorer_name in results, f"Missing results for {scorer_name}"
        
        # Verify summary statistics
        if "summary" in results[scorer_name]:
            summary = results[scorer_name]["summary"]
            assert "mean" in summary, f"Missing mean in summary for {scorer_name}"
            assert "std" in summary, f"Missing std in summary for {scorer_name}"