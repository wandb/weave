from nbconvert import MarkdownExporter


def make_header(notebook_path):
    github_uri = "wandb/weave/blob/master"
    colab_root = f"https://colab.research.google.com/github/{github_uri}"
    colab_path = f"{colab_root}/{notebook_path}"
    github_path = f"https://github.com/{github_uri}/{notebook_path}"

    return f"""---
---

:::tip[This is a notebook]

<a href="{colab_path}" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="{github_path}" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::


"""


def export_notebook(notebook_path, output_path):
    exporter = MarkdownExporter()
    output, resources = exporter.from_filename(notebook_path)

    output = make_header(notebook_path) + output

    with open(output_path, "w") as f:
        f.write(output)


def main():
    export_notebook(
        "./notebooks/example.ipynb", "./docs/reference/gen_notebooks/example.md"
    )


if __name__ == "__main__":
    main()
