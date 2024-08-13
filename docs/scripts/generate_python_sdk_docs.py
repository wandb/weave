# Run this to re-generate Weave API docs from code.


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


def fix_factor(text):
    # When we have a field whose default is a factor function, the
    # emitted payload is `<factory>`, which breaks the markdown parser.
    return text.replace("<factory>", "&lt;factory&gt;")


def fix_imgs(text):
    # Images (used for source code tags) are not closed. While many
    # html parsers handle this, the markdown parser does not. This
    # function fixes that.
    # Example:
    # <img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square">
    # becomes
    # <img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" />

    # This regex matches the img tag and captures the attributes
    # and the src attribute.
    pattern = r'<img(.*?)(src=".*?")>'

    # This function replaces the match with the same match, but with
    # a closing slash before the closing bracket.
    def replace_with_slash(match):
        return f"<img{match.group(1)}{match.group(2)} />"

    # Replace all occurrences of the pattern with the function
    text = re.sub(pattern, replace_with_slash, text)

    return text


def fix_style(text):
    # The docgen produces a lot of inline styles, which are not
    # supported by the markdown parser.
    find = ' style="float:right;"'
    replace = ""
    text = text.replace(find, replace)

    return text


def sanitize_markdown(text):
    return fix_style(fix_imgs(fix_factor(text)))


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


def find_and_replace(text, start, end, replace_with, end_optional=False):
    start_idx = text.find(start)
    if start_idx == -1:
        return text
    end_idx = text.find(end, start_idx + len(start))
    if end_idx == -1:
        if not end_optional:
            return text
        else:
            end_idx = len(text)
    else:
        end_idx += len(end)
    after = text[:start_idx] + replace_with + text[end_idx:]
    return after


def fix_pydantic_model(text, obj, module_name):
    # First, remove these properties that are not useful in the docs
    search_for = """---

#### <kbd>property</kbd> model_extra"""
    up_to = """---"""
    text = find_and_replace(text, search_for, up_to, "---")
    search_for = """---

#### <kbd>property</kbd> model_fields_set"""
    up_to = """---"""
    text = find_and_replace(text, search_for, up_to, "---", end_optional=True)

    text = text.replace(
        """---
---""",
        "---",
    )

    # Next, pydantic does not emit good properties. Fixing that with a dump of the fields:
    # This could be improved in the future
    search_for = """## <kbd>class</kbd>"""
    start_idx = text.find(search_for)
    end_idx = text.find("""---""", start_idx)

    field_summary = "**Pydantic Fields:**\n\n"
    if obj.model_fields:
        for k, v in obj.model_fields.items():
            name = k
            if hasattr(v, "alias") and v.alias != None:
                name = v.alias
            annotation = "Any"
            if hasattr(v, "annotation") and v.annotation != None:
                annotation = str(v.annotation)
                annotation = annotation.replace(module_name + ".", "")

            field_summary += f"- `{name}`: `{annotation}`\n"

        text = text[:end_idx] + field_summary + text[end_idx:]

    if text.endswith("---"):
        text = text[:-3]

    return text


def generate_module_doc_string(module, src_root_path):
    generator = lazydocs.MarkdownGenerator(
        src_base_url="https://github.com/wandb/weave/blob/master",
        src_root_path=src_root_path,
        remove_package_prefix=True,
    )
    markdown_paragraphs = []
    module_name = module.__name__

    # We look for the special __docspec__ attribute, which lists what we want
    # to document, in order.

    def process_item(obj):
        # Very special / hacky handling of pydantic models
        # since the lazydocs library doesn't handle them well.
        if isinstance(obj, type) and issubclass(obj, pydantic.BaseModel):
            markdown_paragraphs.append(
                fix_pydantic_model(generator.class2md(obj), obj, module_name)
            )
        elif callable(obj) and not isinstance(obj, type):
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

            if hasattr(obj, "__module__") and obj.__module__ != module_name:
                continue

            process_item(obj)

    overview = remove_empty_overview_sections(
        sanitize_markdown(generator.overview2md())
    )
    overview = make_links_relative(overview)
    sections = [sanitize_markdown(par) for par in markdown_paragraphs]
    final = "\n\n".join(
        [
            markdown_header(module, module_name.split(".")[-1]),
            markdown_title(module),
            markdown_description(module),
            SECTION_SEPARATOR,
            overview,
            SECTION_SEPARATOR,
            ("\n" + SECTION_SEPARATOR + "\n").join(sections),
        ]
    )

    return final


def doc_module_to_file(module, output_path, module_root_path=None):
    api_docs = generate_module_doc_string(module, module_root_path)
    with open(output_path, "w") as f:
        f.write(api_docs)


def doc_module(module, root_path="./docs/reference/python-sdk", module_root_path=None):
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
    doc_module_to_file(module, target_path, module_root_path)


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

    module_root_path = weave.__file__.split("/weave/__init__.py")[0]
    for module in [
        # TODO: It would be nice to just walk the module hierarchy and generate docs for all modules
        weave,
        client,
        remote_http_trace_server,
        trace_server_interface,
        query,
        feedback,
        util,
    ]:
        doc_module(module, module_root_path=module_root_path)


if __name__ == "__main__":
    main()
