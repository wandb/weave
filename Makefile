.PHONY: docs build

setup-docs-ci:
	pip install -e . playwright lazydocs
	playwright install

	cd docs && \
	npm install --global yarn && \
	npm install

docs: 
	cd docs && make generate_all

build:
	uv build

prepare-release: docs build