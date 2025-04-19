import weave
import subprocess
import json
import os
import difflib
import sys
import random
import itertools
from crewai import Agent, Task, Crew, LLM, Process
from openai import OpenAI
from rich.console import Console
from rich.syntax import Syntax
from rich import print as rprint
from rich.text import Text
from datetime import datetime, timedelta

client = weave.init(project_name="agent-docs")

console = Console()
llm = LLM(model="gpt-4o", temperature=0)

# --- Header ---
def print_agentdocs_header(file_path):
    taglines = [
        "// mission: rewrite with precision",
        "// The name is DOCS, AGENTDOCS.",
        "// target acquired",
        "// scanning for style violations",
        "// commencing edit sweep",
        "// eyes on docs, fingers on keyboard",
        "// operations log: markdown only",
    ]
    chosen = random.choice(taglines)
    filename = os.path.basename(file_path)
    model_version = llm.model if hasattr(llm, 'model') else "LLM"
    header_text = Text(f"[AGENTDOCS]   {chosen}", style="bold white")
    subtext = f"📄 File: {filename}   🤖 Model: {model_version}"
    console.rule(header_text)
    rprint(f"[dim]{subtext}[/dim]")

# --- Agents ---
reader_agent = Agent(
    role="Markdown Reader",
    goal="Read and parse markdown files into structured components",
    backstory="A meticulous agent that accurately splits markdown frontmatter and content.",
    llm=llm
)

linter_agent = Agent(
    role="Vale Linter",
    goal="Run Vale and summarize issues in markdown files",
    backstory="An expert on technical writing standards who uses Vale to find style issues.",
    llm=llm
)

editor_agent = Agent(
    role="GPT Editor",
    goal="Rewrite content to resolve Vale issues and improve clarity",
    backstory="An expert documentation editor who follows the Google style guide.",
    llm=llm
)

diff_agent = Agent(
    role="Diff Tracker",
    goal="Compare original and edited content to show what changed",
    backstory="A specialist in surfacing precise diffs in documentation edits for human review.",
    llm=llm
)

# --- Weaved Functions ---
@weave.op
def summarize_commit_diff():
    """Summarize the latest commit using the full diff."""
    try:
        result = subprocess.run(["git", "show", "HEAD", "--unified=3"],
                                capture_output=True, text=True)
        diff_text = result.stdout
        prompt = f"""You are a documentation assistant. Here's a git diff from the latest commit:

{diff_text}

Summarize the technical changes in 3–5 concise bullet points. 
Assume your audience are users who want to update the codebase docs to accurately reflect the product.

Focus on:
- New features or flags
- Breaking changes
- Updated behavior
- Any schema, API, or CLI changes

Don't write prose — just clean, useful bullets.""" 

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Please summarize the commit."},
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error summarizing commit diff: {e}"

@weave.op
def propose_doc_coverage(summary):
    """Given a commit summary, suggest doc additions or updates."""
    prompt = f"""You are a brilliant technical documentation strategist.

Based on this summary of a recent code commit:

{summary}

Suggest what documentation might need to be updated, added, or clarified. Be specific — mention things like:
- New features to explain
- CLI flags to document
- API behavior that changed
- Example code updates
- Potential user questions or confusion
- Pages that might need updates (like SDK guides or tutorials)

Return the output as a short list of 3–7 doc updates, starting each with a bullet point."""
    
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": "What should we update in the docs?"},
        ]
    )
    return response.choices[0].message.content.strip()

@weave.op
def generate_suggested_docs(outline):
    prompt = f"""You are a senior technical writer.

Based on the following proposed documentation coverage items, generate a Markdown document with proposed content for each point. Use headers, bullet points, and short paragraphs. Focus on clarity, completeness, and actionable sections.

Be factual and concise. Write with a helpful, user-focused tone.

Outline:
{outline}

Generate the content below:"""

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Write the draft doc."},
        ]
    )
    return response.choices[0].message.content.strip()

@weave.op
def read_markdown(file_path):
    with open(file_path, 'r') as f:
        content = f.read()
    parts = content.split('---')
    if len(parts) >= 3:
        return {"frontmatter": parts[1], "content": parts[2]}
    else:
        return {"frontmatter": "", "content": content}

@weave.op
def run_vale(file_path):
    result = subprocess.run(["vale", "--output=JSON", file_path], capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}

@weave.op
def build_prompt(content, vale_output):
    return f"""You are a technical documentation editor. Based on this Vale report:

{json.dumps(vale_output, indent=2)}

Rewrite the content below for clarity and style, following Google style guide rules.

DO NOT modify any code blocks (```), Hugo shortcodes, or URLs. Use active voice, avoid future tense, emojis, or Latin abbreviations. Ensure correct punctuation and heading capitalization.

---

{content}
"""

@weave.op
def call_openai(prompt):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Please rewrite."},
        ]
    )
    return response.choices[0].message.content

@weave.op
def compute_diff(original, edited):
    diff = difflib.unified_diff(
        original.splitlines(),
        edited.splitlines(),
        fromfile='original.md',
        tofile='edited.md',
        lineterm=''
    )
    return "\n".join(diff)

@weave.op
def capture_feedback(accepted: bool, note: str = ""):
    return {"accepted": accepted, "note": note}

# --- Util Functions ---
# --- Format Detection + Routing ---
def detect_doc_format(file_path):
    if file_path.endswith(".ipynb"):
        return "notebook"
    with open(file_path, 'r') as f:
        content = f.read()
    if "+++" in content or "{{<" in content or "shortcode" in content:
        return "hugo"
    elif "---" in content and "sidebar_position" in content:
        return "docusaurus"
    return "markdown"

def route_to_doc_handler(file_path, format):
    if format == "notebook":
        rprint("[bold yellow]⚠️ .ipynb notebooks not yet supported. Skipping.[/bold yellow]")
        return False
    elif format == "hugo":
        rprint("[bold blue]🌐 Hugo-style markdown detected. Applying Hugo-specific handling...[/bold blue]")
        # Placeholder: add Hugo-specific logic here
    elif format == "docusaurus":
        rprint("[bold blue]📚 Docusaurus markdown detected. Applying Docusaurus-specific handling...[/bold blue]")
        # Placeholder: add Docusaurus-specific logic here
    else:
        rprint("[bold white]📄 Generic Markdown detected. Proceeding with standard flow.[/bold white]")
    return True

def fetch_recent_trace_links(file_basename, client, limit=5):
    filter_params = {
        "project_id": "cool-new-team/agent-docs",
        "filter": {
            "started_at": datetime.now() - timedelta(minutes=10),
            "trace_roots_only": True
        },
        "expand_columns": ["inputs"],
        "sort_by": [{"field": "started_at", "direction": "desc"}],
        "include_costs": False,
        "include_feedback": False,
    }

    try:
        calls_stream = client.server.calls_query_stream(filter_params)
        trace_links = []
        for call in itertools.islice(calls_stream, limit):
            if file_basename in (call.display_name or "") or file_basename in str(call.inputs):
                trace_links.append(
                    f"https://wandb.ai/cool-new-team/agent-docs/r/call/{call.trace_id}"
                )
        return trace_links
    except Exception as e:
        return [f"Failed to fetch trace links: {e}"]

# --- Tasks ---
reader_task = Task(
    description="Read markdown from {file_path} and return frontmatter and content.",
    expected_output="A dictionary with 'frontmatter' and 'content'.",
    agent=reader_agent
)

linter_task = Task(
    description="Run Vale linter on the file at {file_path} and return the JSON output.",
    expected_output="Parsed Vale linting results.",
    agent=linter_agent
)

edit_task = Task(
    description="Using Vale output and markdown content, rewrite the content for style improvements.",
    expected_output="Edited markdown content only.",
    agent=editor_agent
)

diff_task = Task(
    description="Compare the original content and the edited content. Show differences in unified diff format.",
    expected_output="Unified diff string showing edits.",
    agent=diff_agent
)

# --- Crew ---
crew = Crew(
    agents=[reader_agent, linter_agent, editor_agent, diff_agent],
    tasks=[reader_task, linter_task, edit_task, diff_task],
    process=Process.sequential,
    verbose=True
)

# --- Main Run ---
def kickoff(file_path, dry_run=False):
    print_agentdocs_header(file_path)

    md_parts = read_markdown(file_path)
    frontmatter = md_parts["frontmatter"]
    original_content = md_parts["content"]

    vale_output = run_vale(file_path)
    prompt = build_prompt(original_content, vale_output)
    edited_content = call_openai(prompt)
    diff_output = compute_diff(original_content, edited_content)

    console.rule("[bold white]📄 Markdown Diff")
    console_width = console.size.width
    syntax_block = Syntax(
        diff_output,
        "diff",
        theme="ansi_dark",
        line_numbers=False,
        word_wrap=False,
        indent_guides=False,
        tab_size=4,
        code_width=console_width
    )
    rprint(syntax_block)

    if not dry_run:
        output_md = f"---{frontmatter}---\n{edited_content}" if frontmatter else edited_content
        with open(file_path, "w") as f:
            f.write(output_md)
        rprint("[bold green]✅ File updated successfully.[/bold green]")
    else:
        rprint("[bold yellow]⚠️ Dry run enabled. No file was modified.[/bold yellow]")

    rprint("\n[bold white]📣 Feedback Time[/bold white]")
    try:
        feedback = input("Did this rewrite look good to you? (y/n): ").strip().lower()
        accepted = feedback in ["y", "yes"]
        note = ""
        if not accepted:
            note = input("Optional: Why not? (feedback note): ").strip()
        capture_feedback(accepted, note)
        rprint("[bold cyan]📝 Feedback logged in Weave.[/bold cyan]")
    except Exception as e:
        rprint(f"[bold red]⚠️ Failed to capture feedback: {e}[/bold red]")

    rprint("\n[bold white]🛰️  Recent Traces for This File:[/bold white]")
    try:
        trace_links = fetch_recent_trace_links(os.path.basename(file_path), client)
        for url in trace_links:
            rprint(f"[bold blue]🔗 {url}[/bold blue]")
    except Exception as e:
        rprint(f"[bold red]Error fetching Weave trace links: {e}[/bold red]")

# --- Entry Point ---
if __name__ == "__main__":
    args = sys.argv[1:]

    if "--help" in args or "-h" in args or not args:
        rprint("""
[bold cyan]AgentDocs CLI[/bold cyan]
Usage:
  [green]python agentdocs.py path/to/file.md[/green]             Run lint + style rewrite
  [green]python agentdocs.py path/to/file.md --dry-run[/green]   Preview changes without saving
  [green]python agentdocs.py --suggest-docs[/green]              Generate doc suggestions from latest commit
  [green]python agentdocs.py --help[/green]                      Show this message
""")
        sys.exit(0)

    suggest_docs = "--suggest-docs" in args
    dry_run = "--dry-run" in args
    file_args = [arg for arg in args if not arg.startswith("--")]

    if suggest_docs:
        rprint("\n[bold white]📚 Suggested Doc Updates from Recent Code Changes:[/bold white]")

        summary = summarize_commit_diff()
        rprint(f"\n[bold green]📝 Commit Summary:[/bold green]\n{summary}")

        doc_outline = propose_doc_coverage(summary)
        rprint(f"\n[bold yellow]📘 Suggested Documentation Coverage:[/bold yellow]\n{doc_outline}")

        draft = generate_suggested_docs(doc_outline)
        rprint("\n[bold green]📄 Draft Doc Output (pre-style-check):[/bold green]\n")
        rprint(draft)

        # Save raw draft
        temp_input = "temp_raw.md"
        with open(temp_input, "w") as f:
            f.write(draft)

        # Lint + style edit
        md_parts = read_markdown(temp_input)
        frontmatter = md_parts["frontmatter"]
        original_content = md_parts["content"]
        vale_output = run_vale(temp_input)
        prompt = build_prompt(original_content, vale_output)
        edited = call_openai(prompt)

        # Get commit hash for filename
        short_sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True
        ).stdout.strip()
        final_filename = f"{short_sha}-suggest-docs.md"

        with open(final_filename, "w") as f:
            output = f"---{frontmatter}---\n{edited}" if frontmatter else edited
            f.write(output)

        rprint(f"\n[bold cyan]✅ Style-checked draft written to:[/bold cyan] [green]{final_filename}[/green]")
        sys.exit(0)

    if not file_args:
        rprint("[bold red]❌ Error:[/bold red] No file path provided.\nUse [green]--help[/green] to see usage.")
        sys.exit(1)

    file_arg = file_args[0]
    kickoff(file_arg, dry_run=dry_run)
