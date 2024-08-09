# Run this to re-generate Weave API docs from code.


import inspect
import os
import re

import lazydocs
import pydantic

MARKDOWN_HEADER = """"""
SECTION_SEPARATOR = "---"


def markdown_header(module, title=None):
    if title is None:
        title = module.__name__
    return f"""---
sidebar_label: {title}
---
    """


def markdown_title(module):
    return f"# {module.__name__}"


def markdown_description(module):
    return module.__doc__ or ""


def sanitize_markdown(text):
    return text.replace("<factory>", "&lt;factory&gt;")


def remove_empty_overview_sections(overview):
    overview = overview.replace(
        """## Functions

- No functions""",
        "",
    )
    overview = overview.replace(
        """## Modules

- No modules""",
        "",
    )
    overview = overview.replace(
        """## Classes

- No classes""",
        "",
    )
    return overview


def make_links_relative(text):
    """In our docgen setup, we don't necessarily document the symbol where
    it is defined. Sometimes we are documenting it where it is re-exported.

    The result is that the default links are broken. This function fixes
    that by making all links relative! How sick.
    """
    # Your regex pattern adjusted for Python. Thanks GPT (:
    pattern = r"^- \[.*\]\((.\/.*)#(.*)\)"

    # Function to replace the first match group with an empty string
    def replace_with_empty(match):
        # match.group(1) corresponds to the first capture group (file part)
        # match.group(0) corresponds to the entire matched string
        return match.group(0).replace(match.group(1), "")

    # Replace all occurrences of match[0] (the file part) with an empty string
    return re.sub(pattern, replace_with_empty, text, flags=re.MULTILINE)


def generate_module_doc_string(module):
    generator = lazydocs.MarkdownGenerator(remove_package_prefix=True)
    markdown_paragraphs = []

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

    overview = remove_empty_overview_sections(
        sanitize_markdown(generator.overview2md())
    )
    overview = make_links_relative(overview)
    sections = [sanitize_markdown(par) for par in markdown_paragraphs]
    final = "\n\n".join(
        [
            markdown_header(module, module.__name__.split(".")[-1]),
            markdown_title(module),
            markdown_description(module),
            SECTION_SEPARATOR,
            overview,
            SECTION_SEPARATOR,
            ("\n" + SECTION_SEPARATOR + "\n").join(sections),
        ]
    )

    return final


def doc_module_to_file(module, output_path):
    api_docs = generate_module_doc_string(module)
    with open(output_path, "w") as f:
        f.write(api_docs)


def doc_module(module, root_path="./docs/reference/python-sdk"):
    module_path = module.__name__
    path_parts = module_path.split(".")
    file_name = module_path + ".md"

    target_dir = root_path + "/" + "/".join(path_parts[:-1])
    # Special case for __init__ modules. This allows
    # the sidebar header to also be the index page.
    if module.__file__.endswith("__init__.py"):
        target_dir = target_dir + "/" + path_parts[-1]
        file_name = "index.md"
    target_path = target_dir + "/" + file_name

    os.makedirs(target_dir, exist_ok=True)
    doc_module_to_file(module, target_path)


def main():
    import weave
    from weave import feedback
    from weave import weave_client as client
    from weave.trace import util
    from weave.trace_server import (
        remote_http_trace_server,
        trace_server_interface,
    )
    from weave.trace_server.interface import query

    # TODO: It would be nice to just walk the module hierarchy and generate docs for all modules
    doc_module(weave)
    doc_module(client)
    doc_module(remote_http_trace_server)
    doc_module(trace_server_interface)
    doc_module(query)
    doc_module(feedback)
    doc_module(util)


if __name__ == "__main__":
    main()
