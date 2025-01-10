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

prepare-release: docs build

synchronize-base-object-schemas:
	cd weave && make generate_base_object_schemas && \
	cd ../weave-js && yarn generate-schemas
