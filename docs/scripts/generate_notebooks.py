import argparse
import os
import re
import tempfile

import nbformat
from nbconvert import MarkdownExporter


def make_header(notebook_path):
    github_uri = "wandb/weave/blob/master/docs"
    colab_root = f"https://colab.research.google.com/github/{github_uri}"
    colab_path = f"{colab_root}/{notebook_path}"
    github_path = f"https://github.com/{github_uri}/{notebook_path}"

    return f"""

:::tip[This is a notebook]

<a href="{colab_path}" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="{github_path}" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::


"""


def remove_outputs(notebook_path):
    with open(notebook_path, encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)

    for cell in nb.cells:
        if cell.cell_type == "code":
            cell.outputs = []
            cell.execution_count = None

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".ipynb", delete=False
    ) as temp_file:
        nbformat.write(nb, temp_file)
        temp_path = temp_file.name
    return temp_path


def export_notebook(notebook_path, output_path):
    # Remove outputs before processing
    temp_path = remove_outputs(notebook_path)

    exporter = MarkdownExporter()
    output, resources = exporter.from_filename(temp_path)

    # Clean up the temporary file
    os.unlink(temp_path)

    extract_meta = ""
    meta_mark_start = "<!-- docusaurus_head_meta::start\n"
    meta_mark_end = "docusaurus_head_meta::end -->\n"
    if meta_mark_start in output and meta_mark_end in output:
        start = output.index(meta_mark_start)
        end = output.index(meta_mark_end)
        extract_meta = output[start + len(meta_mark_start) : end]
        output = output[:start] + output[end + len(meta_mark_end) :]

    output = extract_meta + make_header(notebook_path) + output

    # Fixes image paths by replacing markdown links containing '../docs/' with '/docs/'
    pattern = re.compile(
        r"""
        \(
        (
            \.\./docs/
            .*?
        )
        \)
    """,
        re.VERBOSE,
    )

    replacement = r"(/\1)"

    output = pattern.sub(replacement, output)

    with open(output_path, "w") as f:
        f.write(output)


def export_all_notebooks_in_primary_dir():
    import os

    for filename in os.listdir("./notebooks"):
        if filename.endswith(".ipynb"):
            export_notebook(
                f"./notebooks/{filename}",
                f"./docs/reference/gen_notebooks/{filename.replace('.ipynb', '.md')}",
            )


def main():
    parser = argparse.ArgumentParser(
        description="Convert Python notebooks to Markdown docs."
    )
    parser.add_argument(
        "notebook_path",
        nargs="?",
        help="Optional path to a single .ipynb file to convert",
    )
    args = parser.parse_args()

    if args.notebook_path:
        notebook_path = args.notebook_path
        if not notebook_path.endswith(".ipynb"):
            print("ERROR: The provided file must be a .ipynb notebook.")
            return

        base_name = os.path.basename(notebook_path).replace(".ipynb", ".md")
        output_path = f"./docs/reference/gen_notebooks/{base_name}"
        export_notebook(notebook_path, output_path)
        print(f"Exported {notebook_path} to {output_path}")
    else:
        export_all_notebooks_in_primary_dir()
        export_notebook(
            "./intro_notebook.ipynb",
            "./docs/reference/gen_notebooks/01-intro_notebook.md",
        )
        print("All notebooks exported.")


if __name__ == "__main__":
    main()
