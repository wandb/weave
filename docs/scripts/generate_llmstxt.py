from pathlib import Path
import yaml
import re
import os

def is_optional(file_path: Path) -> bool:
    """Check if file should be in Optional section."""
    path_str = str(file_path)
    return any([
        'integrations' in path_str,
        'integration' in file_path.stem.lower(),
        'gen_notebooks' in path_str,
        'examples' in path_str,
        'reference' in path_str,
        '/api/' in path_str,
        file_path.name.startswith(('example-', 'api-'))
    ])

def get_section(file_path: Path) -> str:
    """Determine section for file."""
    if is_optional(file_path):
        return "Optional"
    
    if any([
        file_path.name in ['introduction.md', 'quickstart.md'],
        '/guides/' in str(file_path),
        file_path.parent == Path('.')
    ]):
        return "Docs"
    
    return "Docs"

def generate_llms_txt(docs_dir: Path, output_file: Path):
    content = [
        "# Weave",
        "> Weave is a lightweight toolkit for tracking and evaluating LLM applications, built by Weights & Biases.",
        "",
        "This document contains links to all the documentation for Weave.",
        ""
    ]

    sections = {"Docs": [], "Optional": []}
    github_base = "https://raw.githubusercontent.com/wandb/weave/master/docs/docs"

    for md_file in docs_dir.rglob('*.[mM][dD]*'):
        if any(part.startswith('.') for part in md_file.parts) or md_file.suffix == '.ipynb':
            continue

        relative_path = md_file.relative_to(docs_dir)
        
        if relative_path.stem == 'index' and get_section(md_file) == "Optional":
            continue

        display_title = relative_path.parent.name if relative_path.stem == 'index' else relative_path.stem
        url_path = str(relative_path).replace('\\', '/')
        entry = f"- [{display_title}]({github_base}/{url_path}): "
        section = get_section(md_file)
        sections[section].append((relative_path.parent == Path('.'), entry))

    # Write sections
    for section_name in ["Docs", "Optional"]:
        if sections[section_name]:
            content.append(f"## {section_name}")
            content.append("")
            sorted_entries = sorted(sections[section_name], key=lambda x: (not x[0], x[1]))
            content.extend(entry[1] for entry in sorted_entries)
            content.append("")

    output_file.write_text('\n'.join(content))

def main():
    # Get the root directory of the project (adjust as needed)
    script_dir = Path(__file__).resolve().parent
    root_dir = script_dir.parent  # Assuming the script is in "docs/scripts"
    
    docs_dir = root_dir / "docs"
    output_file = root_dir / "static" / "llms.txt"

    # Debugging output
    print(f"Docs directory: {docs_dir}")
    print(f"Output file: {output_file}")

    # Ensure the static directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Call the function
    generate_llms_txt(docs_dir=docs_dir, output_file=output_file)

if __name__ == "__main__":
    main()