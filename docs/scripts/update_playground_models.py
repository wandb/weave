# This is a script to update the markdown file with the latest models from the TS file.
# It is used to keep the markdown file in sync with the TS file.
# It is run automatically when you run `make update_playground_models`.

# This is fully vibe coded, but it correctly updates the markdown file.

import re
from collections import defaultdict
import os

# Define paths relative to the script location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(
    os.path.join(SCRIPT_DIR, "..", "..")
)  # Use os.path.join for cross-platform compatibility
TS_FILE_PATH = os.path.join(
    PROJECT_ROOT,
    "weave-js",
    "src",
    "components",
    "PagePanelComponents",
    "Home",
    "Browse3",
    "pages",
    "PlaygroundPage",
    "llmMaxTokens.ts",
)
MD_FILE_PATH = os.path.join(
    PROJECT_ROOT, "docs", "docs", "guides", "tools", "playground.md"
)

# --- Configuration ---

# Order and details for providers as they should appear in the markdown
# Mapping: provider_key: (Display Name, Integration Doc Path or None)
PROVIDER_DETAILS = {
    "bedrock": ("Amazon Bedrock", "../integrations/bedrock.md"),
    "anthropic": ("Anthropic", "../integrations/anthropic.md"),
    "azure": ("Azure", "../integrations/azure.md"),
    "gemini": (
        "Google",
        "../integrations/google.md",
    ),  # Note: key is gemini, name is Google
    "groq": ("Groq", "../integrations/groq.md"),
    "openai": ("OpenAI", "../integrations/openai.md"),
    "xai": ("X.AI", None),
    "deepseek": ("Deepseek", None),
}

PROVIDER_ORDER = [
    "bedrock",
    "anthropic",
    "azure",
    "gemini",
    "groq",
    "openai",
    "xai",
    "deepseek",
]

MARKDOWN_START_MARKER = "<!-- LLM_LIST_START, DON'T EDIT THIS SECTION -->\n"
MARKDOWN_END_MARKER = "\n<!-- LLM_LIST_END, DON'T EDIT THIS SECTION -->"

# --- Helper Functions ---


def extract_llm_data(ts_content):
    """Extracts the LLM_MAX_TOKENS object definition using regex."""
    match = re.search(
        r"export const LLM_MAX_TOKENS = ({.*?});", ts_content, re.DOTALL | re.MULTILINE
    )
    if not match:
        raise ValueError("Could not find LLM_MAX_TOKENS object in the TS file.")

    # The captured group is JS object literal syntax, not strict JSON.
    # We need to parse it carefully. Let's use regex again to extract individual entries.
    object_content = match.group(1).strip()

    # Regex to find each model entry: 'model-name': { provider: 'provider_name', ... }
    # This assumes simple structure and doesn't handle nested objects deeply.
    model_pattern = re.compile(r"'([^']+)':\s*{\s*provider:\s*'([^']+)'.*?}", re.DOTALL)

    models = {}
    for model_match in model_pattern.finditer(object_content):
        model_name = model_match.group(1)
        provider = model_match.group(2)
        models[model_name] = {"provider": provider}  # Store relevant info

    if not models:
        raise ValueError("Could not parse any model entries from LLM_MAX_TOKENS.")

    return models


def group_models_by_provider(models_data):
    """Groups models by their provider."""
    grouped = defaultdict(list)
    for model_name, data in models_data.items():
        provider = data.get("provider")
        if provider:
            grouped[provider].append(model_name)
    return grouped


def sort_models(grouped_models):
    """Sorts models alphabetically within each provider group."""
    for provider in grouped_models:
        grouped_models[provider].sort()
    return grouped_models


def format_markdown(sorted_grouped_models):
    """Formats the grouped and sorted models into a markdown string."""
    md_lines = []
    for provider_key in PROVIDER_ORDER:
        if provider_key in sorted_grouped_models:
            display_name, doc_link = PROVIDER_DETAILS.get(
                provider_key, (provider_key.capitalize(), None)
            )

            if doc_link:
                md_lines.append(f"### [{display_name}]({doc_link})")
            else:
                md_lines.append(f"### {display_name}")

            md_lines.append("")  # Add a blank line after the header

            for model_name in sorted_grouped_models[provider_key]:
                md_lines.append(f"- {model_name}")

            md_lines.append("")  # Add a blank line after each provider list

    # Remove the last blank line if it exists
    if md_lines and md_lines[-1] == "":
        md_lines.pop()

    return "\n".join(md_lines)


def update_markdown_file(md_filepath, new_content):
    """Reads the markdown file, replaces the content between markers, and writes back."""
    try:
        with open(md_filepath, "r", encoding="utf-8") as f:
            md_content = f.read()
    except FileNotFoundError:
        print(f"Error: Markdown file not found at {md_filepath}")
        return

    # Use regex to find and replace content between markers
    # re.DOTALL makes . match newlines
    pattern = re.compile(
        f"({re.escape(MARKDOWN_START_MARKER)}\\n)(.*?)(\n{re.escape(MARKDOWN_END_MARKER)})",
        re.DOTALL,
    )

    # --- DEBUGGING START ---
    # match = pattern.search(md_content)
    # if match:
    #     print("DEBUG: Regex pattern found a match.")
    #     print(f"DEBUG: Group 1 (Start Marker + NL): {repr(match.group(1))}")
    #     # print(f"DEBUG: Group 2 (Content): {repr(match.group(2))}") # Optional: might be long
    #     print(f"DEBUG: Group 3 (NL + End Marker): {repr(match.group(3))}")
    # else:
    #     print("DEBUG: Regex pattern did NOT find a match.")
    # --- DEBUGGING END ---

    # Ensure the new content ends with a newline if it's not empty,
    # and is properly placed between the markers with surrounding newlines.
    replacement_content = f"\\1{new_content}\\3" if new_content else f"\\1\\3"

    new_md_content, num_replacements = pattern.subn(replacement_content, md_content)

    # --- DEBUGGING START ---
    # print("\n------ DEBUG: Content to be written: ------")
    # print(new_md_content)
    # print("------ DEBUG: End of content ------\n")
    # --- DEBUGGING END ---

    if num_replacements == 0:
        print(
            f"Error: Could not find markers '{MARKDOWN_START_MARKER}' and '{MARKDOWN_END_MARKER}' in {md_filepath}"
        )
        return

    if num_replacements > 1:
        print(
            f"Warning: Found multiple instances of the markers in {md_filepath}. Replacing only the first one."
        )
        # If subn replaced more than one, it might be an issue. Let's proceed but warn.

    try:
        with open(md_filepath, "w", encoding="utf-8") as f:
            f.write(new_md_content)
        print(f"Successfully updated model list in {md_filepath}")
    except IOError as e:
        print(f"Error writing updated content to {md_filepath}: {e}")
    # print("DEBUG: File writing is currently commented out for debugging.")


# --- Main Execution ---


def main():
    print(f"Reading TypeScript file: {TS_FILE_PATH}")
    try:
        with open(TS_FILE_PATH, "r", encoding="utf-8") as f:
            ts_content = f.read()
    except FileNotFoundError:
        print(f"Error: TypeScript file not found at {TS_FILE_PATH}")
        return
    except IOError as e:
        print(f"Error reading TypeScript file: {e}")
        return

    print("Extracting LLM data...")
    try:
        models_data = extract_llm_data(ts_content)
    except ValueError as e:
        print(f"Error processing TS file: {e}")
        return

    print(f"Found {len(models_data)} models.")

    print("Grouping models by provider...")
    grouped_models = group_models_by_provider(models_data)

    print("Sorting models...")
    sorted_grouped_models = sort_models(grouped_models)

    print("Formatting markdown...")
    markdown_output = format_markdown(sorted_grouped_models)

    print(f"Updating markdown file: {MD_FILE_PATH}")
    update_markdown_file(MD_FILE_PATH, markdown_output)


if __name__ == "__main__":
    main()
