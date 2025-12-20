.PHONY: build

build:
	uv build

prerelease-dry-run:
	uv run ./scripts/prerelease_dry_run.py

prepare-release: build

synchronize-base-object-schemas:
	cd weave && make generate_base_object_schemas && \
	cd ../../../../frontends/weave && yarn generate-schemas
