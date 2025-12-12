import marimo

__generated_with = "0.18.3"
app = marimo.App(width="medium")

with app.setup:
    # Initialization code that runs before aimport weave
    import weave
    import openai
    from typing import Annotated
    from weave.type_wrappers.Marimo import expose_controls
    import marimo as mo

    model_dropdown = mo.ui.dropdown(options=["gpt-4o-mini", "gpt-5-nano"], value="gpt-4o-mini")


    client = weave.init("marimo-wiggle")


@app.cell
def _():
    # Wiggle
    return


@app.cell(hide_code=True)
def _():
    mo.image("https://preview.redd.it/what-is-going-on-w-wigglytuff-in-the-new-shining-revelry-v0-66cje7igryre1.jpg?width=640&crop=smart&auto=webp&s=d93df5d9e49c81dbd9290cc71ba6155c793ce9e2")
    return


@app.function
@weave.op
def func(
    model: Annotated[str, mo.ui.dropdown(options=["gpt-4o-mini", "gpt-5-nano"], value="gpt-4o-mini")],
    max_output_tokens: Annotated[int, mo.ui.slider(start=20, stop=500, step=20, value=100)],
    topic: Annotated[str, mo.ui.text(value="Tell me a short story")],
    unhinged: Annotated[bool, mo.ui.switch()]
) -> str:
    if unhinged:
        topic += "and make it unhinged"
    
    resp = openai.responses.create(model=model, input=topic,  max_output_tokens=max_output_tokens)
    return resp.output_text


@app.cell
def _():
    controls = expose_controls(func)
    controls
    return (controls,)


@app.cell
def _(controls):
    res = func(**controls.value)
    print(res)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
