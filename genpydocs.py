import lazydocs


MARKDOWN_HEADER = """---
hide_table_of_contents: true
---
"""


def doc_module(module):
    markdown_paragraphs = []

    generator = lazydocs.MarkdownGenerator()
    markdown_paragraphs.append(module.__doc__)
    for obj in module.__docspec__:
        markdown_paragraphs.append(generator.func2md(obj))
    return MARKDOWN_HEADER + "\n---\n".join(markdown_paragraphs)


def main():
    from weave import api

    api_docs = doc_module(api)
    with open("docs/docs/api-reference/python/weave.md", "w") as f:
        f.write(api_docs)


if __name__ == "__main__":
    main()
