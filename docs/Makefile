generate_service_api_docs:
	mkdir -p ./docs/reference/service-api
	rm -rf ./docs/reference/service-api
	mkdir -p ./docs/reference/service-api
	python scripts/generate_service_api_spec.py
	yarn docusaurus gen-api-docs all

generate_python_sdk_docs:
	mkdir -p ./docs/reference/python-sdk
	rm -rf ./docs/reference/python-sdk
	mkdir -p ./docs/reference/python-sdk
	python scripts/generate_python_sdk_docs.py

generate_notebooks_docs:
	mkdir -p ./docs/reference/gen_notebooks
	rm -rf ./docs/reference/gen_notebooks
	mkdir -p ./docs/reference/gen_notebooks
	python scripts/generate_notebooks.py

generate_reference_docs: generate_service_api_docs generate_python_sdk_docs generate_notebooks_docs
	yarn build
