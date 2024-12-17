from transformers import AutoModelForSequenceClassification, AutoTokenizer
import os
import shutil

# Clean existing directories to ensure fresh start
dirs_to_clean = [
    'coherence', 'toxicity', 'bias', 'context_relevance',
    'hallucination', 'faithfulness', 'test-bias-scorer',
    'test-toxicity-scorer', 'test-coherence-scorer'
]

for dir_name in dirs_to_clean:
    path = f"tests/weave_models/{dir_name}"
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)

models = {
    # Original models
    "coherence": "wandb/coherence_scorer",
    "toxicity": "wandb/celadon",
    "bias": "wandb/bias_scorer",
    "context_relevance": "bert-base-uncased",
    "hallucination": "facebook/bart-large-mnli",
    "faithfulness": "facebook/bart-large-mnli",

    # Test-specific models with their configurations
    "test-bias-scorer": {
        "base_model": "bert-base-uncased",
        "num_labels": 2,  # Binary classification for bias
        "problem_type": "multi_label_classification"
    },
    "test-toxicity-scorer": {
        "base_model": "bert-base-uncased",
        "num_labels": 5,  # Five toxicity categories
        "problem_type": "multi_label_classification"
    },
    "test-coherence-scorer": {
        "base_model": "bert-base-uncased",
        "num_labels": 2,  # Binary classification for coherence
        "problem_type": "single_label_classification"
    }
}

for name, model_info in models.items():
    path = f"tests/weave_models/{name}"
    print(f"Downloading model for {name} to {path}...")
    try:
        if isinstance(model_info, dict):
            # Test-specific model configuration
            model_obj = AutoModelForSequenceClassification.from_pretrained(
                model_info["base_model"],
                num_labels=model_info["num_labels"],
                problem_type=model_info["problem_type"],
                trust_remote_code=True
            )
            tokenizer = AutoTokenizer.from_pretrained(
                model_info["base_model"],
                trust_remote_code=True
            )
        else:
            # Original model loading
            model_obj = AutoModelForSequenceClassification.from_pretrained(
                model_info,
                trust_remote_code=True
            )
            tokenizer = AutoTokenizer.from_pretrained(
                model_info,
                trust_remote_code=True
            )

        # Save to test directory
        model_obj.save_pretrained(path)
        tokenizer.save_pretrained(path)

        # Log model info
        print(f"Successfully downloaded model for {name}")
        print(f"Number of labels: {model_obj.config.num_labels}")
        print(f"Model type: {model_obj.config.model_type}")
    except Exception as e:
        print(f"Error downloading model for {name}: {e}")
