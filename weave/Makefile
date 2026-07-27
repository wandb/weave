update_costs:
	python trace_server/costs/update_costs.py

generate_base_object_schemas:
	python ../scripts/generate_base_object_schemas.py

update_model_providers:
	python trace_server/model_providers/model_providers.py

update_model_catalog:
	uv run trace_server/model_providers/catalog_augment_hf.py

sync_model_catalog:
	uv run trace_server/model_providers/catalog_augment_hf.py --skip-hugging-face
