generate_panel_instructions:
	jupyter nbconvert --to markdown examples/template_instructions/*.ipynb --output-dir weave/panels_py/instructions/


.integration-deps: requirements.test.txt requirements.txt
	pip install -r requirements.test.txt
	touch .integration-deps


integration: .integration-deps
	supervisord -c supervisord.conf
