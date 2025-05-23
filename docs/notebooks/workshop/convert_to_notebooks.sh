#!/bin/bash

# Convert Python files to Jupyter notebooks using jupytext
# This is useful if you want to run the workshop in notebook format

echo "Converting Python files to Jupyter notebooks..."

jupytext --to notebook weave_features_workshop.py workshop_evaluation_examples.py

echo "✅ Conversion complete!"
echo "Generated files:"
echo "  - weave_features_workshop.ipynb"
echo "  - workshop_evaluation_examples.ipynb" 