.PHONY: docs build

docs: 
	cd docs && make generate_all

build:
	uv build

prepare-release: docs build