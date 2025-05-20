#!/usr/bin/env python3

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

MAX_TOKENS = 2000  # Approximate word count cap for non-core entries
BASE_URL = "https://weave-docs.wandb.ai/"

CATEGORY_HINTS = {
    "guides/integrations": "Integrations",
    "guides/tracking": "Tracking",
    "guides/tools": "Tools",
    "guides/platform": "Platform",
    "guides/evaluation": "Evaluation",
    "guides/core-types": "Core Types",
    "reference/gen_notebooks": "Example Notebooks",
    "reference/service-api": "Service API",
    "reference/typescript-sdk": "TypeScript SDK",
    "reference/python-sdk": "Python SDK",
    "tutorial": "Tutorials",
    "quickstart": "Quickstart",
    "introduction": "Introduction",
    "faq": "FAQs",
}


def is_optional(file_path: Path) -> bool:
    path_str = str(file_path)
    return any(
        [
            "gen_notebooks" in path_str,
            "examples" in path_str,
            file_path.name.startswith("example-"),
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


def categorize(file_path: Path) -> str:
    path_str = file_path.as_posix()
    for hint_path, category in CATEGORY_HINTS.items():
        if hint_path in path_str:
            return category
    return "Other"


def strip_frontmatter(content: str) -> str:
    return re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, flags=re.DOTALL)


def strip_jsx(content: str) -> str:
    content = re.sub(r"import .*? from .*?;\n", "", content)
    content = re.sub(r"<.*?>", "", content)
    return content


def replace_callouts(content: str) -> str:
    content = re.sub(
        r":::note\s*\n(.*?)\n:::", r"> 💡 **Note**: \1", content, flags=re.DOTALL
    )
    content = re.sub(
        r":::tip\s*\n(.*?)\n:::", r"> 🌟 **Tip**: \1", content, flags=re.DOTALL
    )
    content = re.sub(
        r":::important\s*\n(.*?)\n:::",
        r"> 🚨 **Important**: \1",
        content,
        flags=re.DOTALL,
    )
    return content


def remove_highlight_lines(content: str) -> str:
    return re.sub(r"^\s*# highlight-next-line\n", "", content, flags=re.MULTILINE)


def remove_images(content: str) -> str:
    return re.sub(r"!\[.*?\]\(.*?\)", "", content)


def clean_markdown(content: str) -> str:
    content = strip_frontmatter(content)
    content = strip_jsx(content)
    content = replace_callouts(content)
    content = remove_highlight_lines(content)
    content = remove_images(content)
    return content.strip()


def generate_llms_full_outputs(
    docs_dir: Path, txt_output: Path, json_output: Path, split_by_category: bool = False
):
    sections: dict[str, dict[str, list[tuple[str, str, str]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    json_entries = []

    for md_file in docs_dir.rglob("*.md*"):
        if any(part.startswith(".") for part in md_file.parts):
            continue

        raw_content = md_file.read_text(encoding="utf-8")
        section = get_section(md_file)
        category = categorize(md_file)
        title = extract_title(
            raw_content, md_file.stem.replace("-", " ").replace("_", " ").title()
        )
        cleaned = clean_markdown(raw_content)

        if section == "Optional" and len(cleaned.split()) > MAX_TOKENS:
            cleaned = (
                " ".join(cleaned.split()[:MAX_TOKENS]) + "\n\n> Content truncated."
            )

        url_path = md_file.relative_to(docs_dir).with_suffix("").as_posix()
        url = f"{BASE_URL}{url_path}"

        md_block = f"<!--- {section}: {category} -->\n<!--- {title} -->\n\n# {title}\n\n{cleaned}\n\n[Source]({url})"
        sections[section][category].append((title, url, md_block))

        json_entries.append(
            {
                "title": title,
                "url": url,
                "section": section,
                "category": category,
                "content": cleaned,
            }
        )

    toc_lines = ["## Table of Contents", ""]
    for section_name in ["Docs", "Optional"]:
        for category in sorted(sections[section_name].keys()):
            toc_lines.append(f"### {category}")
            for title, url, _ in sections[section_name][category]:
                toc_lines.append(f"- [{title}]({url})")
            toc_lines.append("")

    full_md = [
        "# Weave Documentation",
        "> Consolidated LLM-friendly documentation for Weave.",
        "",
        *toc_lines,
    ]

    for section_name in ["Docs", "Optional"]:
        for category in sorted(sections[section_name].keys()):
            full_md.extend(entry for _, _, entry in sections[section_name][category])
            full_md.append("")

    txt_output.write_text("\n\n".join(full_md), encoding="utf-8")
    json_output.write_text(json.dumps(json_entries, indent=2), encoding="utf-8")

    if split_by_category:
        for section_name in sections:
            for category in sections[section_name]:
                filename = f"llms-{category.lower().replace(' ', '_')}.txt"
                category_path = txt_output.parent / filename
                category_content = [
                    entry for _, _, entry in sections[section_name][category]
                ]
                category_path.write_text(
                    "\n\n".join(category_content), encoding="utf-8"
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--categories", action="store_true", help="Generate per-category .txt files"
    )
    args = parser.parse_args()

    generate_llms_full_outputs(
        docs_dir=Path("./docs"),
        txt_output=Path("./static/llms-full.txt"),
        json_output=Path("./static/llms-full.json"),
        split_by_category=args.categories,
    )
