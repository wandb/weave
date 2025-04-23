#!/usr/bin/env python3

from pathlib import Path
import re

def is_optional(file_path: Path) -> bool:
    path_str = str(file_path)
    return any(
        [
            "integrations" in path_str,
            "integration" in file_path.stem.lower(),
            "gen_notebooks" in path_str,
            "examples" in path_str,
            "reference" in path_str,
            "/api/" in path_str,
            file_path.name.startswith(("example-", "api-")),
        ]
    )

def get_section(file_path: Path) -> str:
    return "Optional" if is_optional(file_path) else "Docs"

def strip_frontmatter(content: str) -> str:
    return re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, flags=re.DOTALL)

def strip_jsx(content: str) -> str:
    content = re.sub(r"import .*? from .*?;\n", "", content)
    content = re.sub(r"<.*?>", "", content)
    return content

def replace_callouts(content: str) -> str:
    content = re.sub(r":::note\s*\n(.*?)\n:::", r"> 💡 **Note**: \1", content, flags=re.DOTALL)
    content = re.sub(r":::tip\s*\n(.*?)\n:::", r"> 🌟 **Tip**: \1", content, flags=re.DOTALL)
    content = re.sub(r":::important\s*\n(.*?)\n:::", r"> 🚨 **Important**: \1", content, flags=re.DOTALL)
    return content

def remove_highlight_lines(content: str) -> str:
    return re.sub(r'^\s*# highlight-next-line\n', '', content, flags=re.MULTILINE)

def remove_images(content: str) -> str:
    return re.sub(r'!\[.*?\]\(.*?\)', '', content)

def clean_markdown(content: str) -> str:
    content = strip_frontmatter(content)
    content = strip_jsx(content)
    content = replace_callouts(content)
    content = remove_highlight_lines(content)
    content = remove_images(content)
    return content.strip()

def generate_llms_full_txt(docs_dir: Path, output_file: Path):
    sections: dict[str, list[tuple[str, str]]] = {"Docs": [], "Optional": []}

    for md_file in docs_dir.rglob("*.md*"):
        if any(part.startswith(".") for part in md_file.parts):
            continue

        section = get_section(md_file)
        title = md_file.stem.replace("-", " ").replace("_", " ").title()
        raw_content = md_file.read_text(encoding="utf-8")
        cleaned = clean_markdown(raw_content)
        sections[section].append((title, f"# {title}\n\n{cleaned}"))

    # Generate TOC
    toc_lines = ["## Table of Contents", ""]
    for section_name in ["Docs", "Optional"]:
        for title, _ in sections[section_name]:
            anchor = title.lower().replace(" ", "-")
            toc_lines.append(f"- [{title}](#{anchor})")
    toc_lines.append("")

    # Compile full content
    full_content = [
        "# Weave Documentation",
        "> Consolidated LLM-friendly documentation for Weave.",
        "",
        *toc_lines,
    ]

    for section_name in ["Docs", "Optional"]:
        if sections[section_name]:
            full_content.append(f"# {section_name}")
            full_content.append("")
            full_content.extend(entry for _, entry in sections[section_name])
            full_content.append("")

    output_file.write_text("\n\n".join(full_content), encoding="utf-8")

if __name__ == "__main__":
    generate_llms_full_txt(
        docs_dir=Path("./docs"),
        output_file=Path("./static/llms-full.txt"),
    )
