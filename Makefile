.PHONY: docs build

setup-docs-ci:
	pip install -e .[docs]
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
	cd ../../../../frontends/weave && yarn generate-schemas

generate-bindings:
	uv run tools/codegen/generate.py $(ARGS)