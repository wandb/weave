deps:
	pip install -r requirements.txt
	pip install -r requirements.dev.txt

notebook: deps
	jupyter notebook --port=$(PORT)

engine: deps
	FLASK_ENV=development FLASK_APP=weave.weave_server flask run --port $(PORT)