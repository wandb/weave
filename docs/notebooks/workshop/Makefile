# Weave Workshop Makefile

.PHONY: notebooks check-deps convert help

help:
	@echo "Weave Workshop Commands:"
	@echo "  make notebooks   - Convert Python files to Jupyter notebooks"
	@echo "  make check-deps  - Check if jupytext is installed"
	@echo "  make help        - Show this help message"

notebooks: check-deps
	@echo "Converting Python files to Jupyter notebooks..."
	jupytext --to notebook weave_features_workshop.py workshop_evaluation_examples.py
	@echo "✅ Conversion complete!"
	@echo "Generated files:"
	@echo "  - weave_features_workshop.ipynb"
	@echo "  - workshop_evaluation_examples.ipynb"

check-deps:
	@which jupytext > /dev/null 2>&1 || (echo "❌ jupytext not found. Install with: pip install jupytext" && exit 1) 