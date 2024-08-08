generate_service_api_docs:
	rm -rf ./docs/reference/service-api
	mkdir -p ./docs/reference/service-api
	python scripts/generate_service_api_spec.py
	yarn docusaurus gen-api-docs all

generate_python_sdk_docs:
	rm -rf ./docs/reference/python-sdk
	mkdir -p ./docs/reference/python-sdk
	python scripts/generate_python_sdk_docs.py

generate_reference_docs: generate_service_api_docs generate_python_sdk_docs
	yarn build
