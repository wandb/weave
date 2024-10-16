# Serve

Given a Weave ref to any Weave Model you can run:

```
weave serve <ref>
```

to run a FastAPI server for that model. Visit [http://0.0.0.0:9996/docs](http://0.0.0.0:9996/docs) to query the model interactively.

## Install FastAPI

```bash
pip install fastapi uvicorn
```

## Serve Model

In a terminal, call:

```bash
weave serve <your model ref>
```

Get your model ref by navigating to the model and copying it from the UI. It should look like:
`weave:///your_entity/project-name/YourModel:<hash>`

To use it, navigate to the Swagger UI link, click the predict endpoint and then click "Try it out!".
