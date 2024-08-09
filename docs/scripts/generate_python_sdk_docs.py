# Run this to re-generate Weave API docs from code.


import inspect

import lazydocs
import pydantic

MARKDOWN_HEADER = """
"""


def doc_module(module):
    markdown_paragraphs = []

    generator = lazydocs.MarkdownGenerator()

    markdown_paragraphs.append(module.__doc__ or "")
    # We look for the special __docspec__ attribute, which lists what we want
    # to document, in order.

    def process_item(obj):
        # Very special / hacky handling of pydantic models
        # since the lazydocs library doesn't handle them well.
        if (
            isinstance(obj, type)
            and issubclass(obj, pydantic.BaseModel)
            and obj.__mro__[1] == pydantic.BaseModel
        ):
            _ = generator.class2md(obj)
            text = f"""## <kbd>class</kbd> `{obj.__name__}`
            
```python
{inspect.getsource(obj)}
```
            """
            markdown_paragraphs.append(text)
            return

        if callable(obj) and not isinstance(obj, type):
            markdown_paragraphs.append(generator.func2md(obj))
        elif isinstance(obj, type):
            markdown_paragraphs.append(generator.class2md(obj))
        else:
            pass

    if hasattr(module, "__docspec__"):
        for obj in module.__docspec__:
            process_item(obj)
    else:
        for symbol in dir(module):
            if symbol.startswith("_"):
                continue

            obj = getattr(module, symbol)

            if hasattr(obj, "__module__") and obj.__module__ != module.__name__:
                continue

            process_item(obj)

    markdown_paragraphs.insert(0, generator.overview2md())
    final = MARKDOWN_HEADER + "\n---\n".join(markdown_paragraphs)
    final = final.replace("<factory>", "[]")
    return final


def doc_module_to_file(module, output_path):
    api_docs = doc_module(module)
    with open("./docs/reference/python-sdk/" + output_path, "w") as f:
        f.write(api_docs)


def main():
    import weave
    from weave import feedback
    from weave import weave_client as client
    from weave.trace_server import (
        remote_http_trace_server,
        trace_server_interface,
    )
    from weave.trace_server.interface import query

    # TODO: It would be nice to just walk the module hierarchy and generate docs for all modules
    doc_module_to_file(weave, "weave.md")
    doc_module_to_file(client, "client.md")
    doc_module_to_file(remote_http_trace_server, "remote_http_trace_server.md")
    doc_module_to_file(trace_server_interface, "trace_server_interface.md")
    doc_module_to_file(query, "query.md")
    doc_module_to_file(feedback, "feedback.md")


if __name__ == "__main__":
    main()
