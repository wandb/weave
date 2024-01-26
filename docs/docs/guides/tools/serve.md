---
sidebar_position: 0
hide_table_of_contents: true
---

# Serve

Given a Weave ref to any Weave Model you can run:

```
weave serve <ref>
```

to run a FastAPI server for that model.

## Install FastAPI

```bash
pip install fastapi uvicorn
```

## Serve Model`

In a terminal, call:
```bash
weave serve <your model ref>
```

Get your model ref by navigating to the model and copying it from the UI. It should look like:
`wandb-artifact:///your_entity/project-name/YourModel:<hash>/obj`

To use it, navigate to the Swagger UI link, click the predict endpoint and then click "Try it out!".
 