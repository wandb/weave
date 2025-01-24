from datasets import load_dataset

# Load dataset
ds = load_dataset("rotten_tomatoes", split="validation")

# Access dataset info
print(ds.info)
