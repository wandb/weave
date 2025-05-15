#!/usr/bin/env python3

from pathlib import Path
import re
import json

MAX_TOKENS = 2000  # Approximate word count cap for Optional entries
BASE_URL = "https://weave-docs.wandb.ai/"


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


def extract_title(content: str, fallback: str) -> str:
    match = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if match:
        frontmatter = match.group(1)
        title_match = re.search(r"title:\s*(.+)", frontmatter)
        if title_match:
            return title_match.group(1).strip()
    return fallback


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


def generate_llms_full_outputs(docs_dir: Path, txt_output: Path, json_output: Path):
    sections = {"Docs": [], "Optional": []}
    json_entries = []

    for md_file in docs_dir.rglob("*.md*"):
        if any(part.startswith(".") for part in md_file.parts):
            continue

        raw_content = md_file.read_text(encoding="utf-8")
        section = get_section(md_file)
        title = extract_title(raw_content, md_file.stem.replace("-", " ").replace("_", " ").title())
        cleaned = clean_markdown(raw_content)

        if section == "Optional" and len(cleaned.split()) > MAX_TOKENS:
            cleaned = " ".join(cleaned.split()[:MAX_TOKENS]) + "\n\n> Content truncated."

        url_path = md_file.relative_to(docs_dir).with_suffix("").as_posix()
        url = f"{BASE_URL}{url_path}"

        md_block = f"# {title}\n\n{cleaned}\n\n[Source]({url})"
        sections[section].append((title, url, md_block))

        json_entries.append({
            "title": title,
            "url": url,
            "section": section,
            "content": cleaned
        })

    toc_lines = ["## Table of Contents", ""]
    for section_name in ["Docs", "Optional"]:
        for title, url, _ in sections[section_name]:
            toc_lines.append(f"- [{title}]({url})")
    toc_lines.append("")

    full_md = [
        "# Weave Documentation",
        "> Consolidated LLM-friendly documentation for Weave.",
        "",
        *toc_lines,
    ]

    for section_name in ["Docs", "Optional"]:
        if sections[section_name]:
            full_md.append(f"# {section_name}\n")
            full_md.extend(entry for _, _, entry in sections[section_name])
            full_md.append("")

    txt_output.write_text("\n\n".join(full_md), encoding="utf-8")
    json_output.write_text(json.dumps(json_entries, indent=2), encoding="utf-8")


if __name__ == "__main__":
    generate_llms_full_outputs(
        docs_dir=Path("./docs"),
        txt_output=Path("./static/llms-full.txt"),
        json_output=Path("./static/llms-full.json")
    )
