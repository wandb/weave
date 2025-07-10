.PHONY: docs build

setup-docs-ci:
	pip install uv
	uv venv .venv --python 3.13
	source .venv/bin/activate && \
		uv sync --group docs
	playwright install

	cd docs && \
	npm install --global yarn && \
	npm install

docs: 
	cd docs && make generate_all

build:
	uv build

prerelease-dry-run:
	uv run ./weave/scripts/prerelease_dry_run.py

prepare-release: docs build

synchronize-base-object-schemas:
	cd weave && make generate_base_object_schemas && \
	cd ../weave-js && yarn generate-schemas

generate-bindings:
	python tools/codegen/generate.py $(ARGS)