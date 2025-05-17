import os
import re

import lazydocs
import pydantic

from weave.trace_server_bindings import remote_http_trace_server

MODULE_TITLE_OVERRIDES = {
    "weave": "Weave Core",
    "weave.trace": "Tracing",
    "weave.trace.feedback": "User Feedback API",
    "weave.trace.op": "Operations",
    "weave.trace.util": "Utilities",
    "weave.trace.weave_client": "Tracing Client",
    "weave.trace_server": "Trace Server",
    "weave.trace_server.interface": "Server Interface",
    "weave.trace_server.trace_server_interface": "Trace Server Bindings",
    "weave.trace_server_bindings": "Remote Bindings",
    "weave.trace_server_bindings.remote_http_trace_server": "Remote HTTP Server",
}


# Grouping for sidebar categories
MODULE_CATEGORY_OVERRIDES = {
    "weave": "Core Concepts",
    "weave.trace": "Core Concepts",
    "weave.trace.op": "Trace Management",
    "weave.trace.util": "Trace Management",
    "weave.trace.weave_client": "Trace Management",
    "weave.trace.feedback": "Feedback System",
    "weave.trace_server.interface": "Trace Server",
    "weave.trace_server.interface.query": "Trace Server",
    "weave.trace_server.remote_http_trace_server": "Remote Server Bindings",
}

SECTION_SEPARATOR = "---"


def markdown_header(module, title=None):
    module_name = module.__name__
    title = MODULE_TITLE_OVERRIDES.get(module_name, module_name.split(".")[-1])

    frontmatter_lines = [f"sidebar_label: {title}"]

    return f"""---
{chr(10).join(frontmatter_lines)}
---"""



def markdown_title(module):
    return f"# {module.__name__}"


def markdown_description(module):
    return module.__doc__ or ""

def generate_category_indexes(root_path="./docs/reference/python-sdk"):
    category_descriptions = {
        "Core Concepts": "Core Weave APIs and foundational utilities.",
        "Trace Management": "Client-side tools for trace instrumentation and handling.",
        "Feedback System": "APIs for collecting and interacting with user feedback.",
        "Trace Server": "Server-side components for storing and querying trace data.",
        "Remote Server Bindings": "HTTP-based access and bindings for trace servers.",
    }

    for category in set(MODULE_CATEGORY_OVERRIDES.values()):
        folder_name = category.replace(" ", "_")
        target_dir = os.path.join(root_path, folder_name)
        os.makedirs(target_dir, exist_ok=True)
        index_path = os.path.join(target_dir, "index.md")

        with open(index_path, "w") as f:
            f.write(f"""---
sidebar_label: {category}
---

{category_descriptions.get(category, "This section documents modules for " + category.lower())}
""")


def fix_factor(text):
    return text.replace("<factory>", "&lt;factory&gt;")


def fix_imgs(text):
    pattern = r'<img(.*?)(src=".*?")>'
    def replace_with_slash(match):
        return f"<img{match.group(1)}{match.group(2)} />"
    return re.sub(pattern, replace_with_slash, text)


def fix_style(text):
    return text.replace(' style="float:right;"', "")


def sanitize_markdown(text):
    return fix_style(fix_imgs(fix_factor(text)))


def remove_empty_overview_sections(overview):
    for block in ["Functions", "Modules", "Classes"]:
        overview = overview.replace(f"## {block}\n\n- No {block.lower()}", "")
    return overview


def make_links_relative(text):
    pattern = r"^- \[.*\]\((.\/.*)#(.*)\)"
    def replace_with_empty(match):
        return match.group(0).replace(match.group(1), "")
    return re.sub(pattern, replace_with_empty, text, flags=re.MULTILINE)


def find_and_replace(text, start, end, replace_with, end_optional=False):
    start_idx = text.find(start)
    if start_idx == -1:
        return text
    end_idx = text.find(end, start_idx + len(start))
    if end_idx == -1 and end_optional:
        end_idx = len(text)
    elif end_idx == -1:
        return text
    else:
        end_idx += len(end)
    return text[:start_idx] + replace_with + text[end_idx:]


def fix_pydantic_model(text, obj, module_name):
    text = find_and_replace(text, "#### <kbd>property</kbd> model_extra", "---", "---")
    text = find_and_replace(text, "#### <kbd>property</kbd> model_fields_set", "---", "---", True)
    text = text.replace("---\n---", "---")

    search_for = "## <kbd>class</kbd>"
    start_idx = text.find(search_for)
    end_idx = text.find("---", start_idx)

    field_summary = "**Pydantic Fields:**\n\n"
    if obj.model_fields:
        for k, v in obj.model_fields.items():
            name = k if not getattr(v, "alias", None) else v.alias
            annotation = str(getattr(v, "annotation", "Any")).replace(module_name + ".", "")
            field_summary += f"- `{name}`: `{annotation}`\n"
        text = text[:end_idx] + field_summary + text[end_idx:]

    return text.rstrip("---")


def generate_module_doc_string(module, src_root_path):
    generator = lazydocs.MarkdownGenerator(
        src_base_url="https://github.com/wandb/weave/blob/master",
        src_root_path=src_root_path,
        remove_package_prefix=True,
    )
    markdown_paragraphs = []
    module_name = module.__name__

    def process_item(obj):
        if isinstance(obj, type) and issubclass(obj, pydantic.BaseModel):
            markdown_paragraphs.append(fix_pydantic_model(generator.class2md(obj), obj, module_name))
        elif callable(obj) and not isinstance(obj, type):
            markdown_paragraphs.append(generator.func2md(obj))
        elif isinstance(obj, type):
            markdown_paragraphs.append(generator.class2md(obj))

    if hasattr(module, "__docspec__"):
        for obj in module.__docspec__:
            process_item(obj)
    else:
        for symbol in dir(module):
            if symbol.startswith("_"):
                continue
            obj = getattr(module, symbol)
            if getattr(obj, "__module__", None) != module_name:
                continue
            process_item(obj)

    overview = make_links_relative(remove_empty_overview_sections(sanitize_markdown(generator.overview2md())))
    sections = [sanitize_markdown(par) for par in markdown_paragraphs]

    return "\n\n".join([
        markdown_header(module),
        markdown_title(module),
        markdown_description(module),
        SECTION_SEPARATOR,
        overview,
        SECTION_SEPARATOR,
        ("\n" + SECTION_SEPARATOR + "\n").join(sections),
    ])


def doc_module_to_file(module, output_path, module_root_path=None):
    api_docs = generate_module_doc_string(module, module_root_path)
    with open(output_path, "w") as f:
        f.write(api_docs)


def doc_module(module, root_path="./docs/reference/python-sdk", module_root_path=None):
    module_path = module.__name__
    file_name = "index.md" if module.__file__.endswith("__init__.py") else module_path.split(".")[-1] + ".md"

    # Use category name as directory if defined
    category = MODULE_CATEGORY_OVERRIDES.get(module_path)
    base_dir = category.replace(" ", "_") if category else "/".join(module_path.split(".")[:-1])

    target_dir = os.path.join(root_path, base_dir)
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, file_name)

    doc_module_to_file(module, target_path, module_root_path)


def main():
    import weave
    from weave.trace import feedback, util
    from weave.trace import op as OpSpec
    from weave.trace import weave_client as client
    from weave.trace_server import trace_server_interface
    from weave.trace_server.interface import query

    module_root_path = weave.__file__.split("/weave/__init__.py")[0]

    generate_category_indexes()

    for module in [
        weave,
        client,
        remote_http_trace_server,
        trace_server_interface,
        query,
        feedback,
        util,
        OpSpec,
    ]:
        doc_module(module, module_root_path=module_root_path)


if __name__ == "__main__":
    main()
