"""Download required models for testing."""

import logging
import os
import shutil

from transformers import BertForSequenceClassification, BertTokenizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def download_models():
    """Download all required models for testing."""
    # Create models directory
    os.makedirs("tests/weave_models", exist_ok=True)

    # Model configurations - using bert-base-uncased for testing
    models = {
        "test-toxicity-scorer": "bert-base-uncased",
        "test-bias-scorer": "bert-base-uncased",
    }

    for model_dir, model_name in models.items():
        full_path = os.path.join("tests/weave_models", model_dir)
        temp_path = os.path.join("tests/weave_models", f"temp_{model_dir}")

        # Clean up any existing temporary directory
        if os.path.exists(temp_path):
            shutil.rmtree(temp_path)

        try:
            logger.info(f"Downloading {model_name} to temporary location {temp_path}")

            # Download to temporary location first
            model = BertForSequenceClassification.from_pretrained(
                model_name,
                num_labels=2,  # Binary classification for toxicity/bias
            )
            tokenizer = BertTokenizer.from_pretrained(model_name)

            # Save model and tokenizer to temporary location
            os.makedirs(temp_path, exist_ok=True)
            model.save_pretrained(temp_path)
            tokenizer.save_pretrained(temp_path)

            # Verify files were saved in temporary location
            required_files = [
                "config.json",
                "pytorch_model.bin",
                "tokenizer.json",
                "vocab.txt",
            ]
            missing_files = [
                f
                for f in required_files
                if not os.path.exists(os.path.join(temp_path, f))
            ]

            if missing_files:
                raise RuntimeError(
                    f"Missing required files in temporary location: {missing_files}"
                )

            # Remove existing model directory if it exists
            if os.path.exists(full_path):
                shutil.rmtree(full_path)

            # Move temporary directory to final location
            shutil.move(temp_path, full_path)
            logger.info(f"Successfully downloaded {model_name} to {full_path}")

        except Exception as e:
            logger.exception(f"Error downloading {model_name}: {str(e)}")
            # Clean up temporary directory if it exists
            if os.path.exists(temp_path):
                shutil.rmtree(temp_path)
            raise

    logger.info("All models downloaded successfully")


if __name__ == "__main__":
    download_models()
