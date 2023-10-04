generate_panel_instructions:
	jupyter nbconvert --to markdown examples/template_instructions/*.ipynb --output-dir weave/panels_py/instructions/

.test-deps-installed.idea: requirements.test.txt requirements.txt requirements.datadog.txt
	pip install -r requirements.test.txt
	touch .test-deps-installed.idea

run-integration: .test-deps-installed.idea
	supervisord -c supervisord.conf
