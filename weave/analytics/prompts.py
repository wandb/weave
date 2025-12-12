"""LLM prompts for trace analysis - based on FAILS prompts."""

# =============================================================================
# Core Definitions
# =============================================================================

TRACE_PATTERN_DEFINITION = """A trace represents a single execution of a system that has been selected for analysis. \
Traces may be selected because they exhibit specific behaviors, contain errors, fail certain criteria, or match other \
filter conditions. Each trace may exhibit issues or patterns such as:

- Incorrect outputs or behaviors
- Formatting problems or structured output errors
- Execution errors or exceptions
- Too many tool calls or infinite loops
- Edge cases or unusual behaviors
- Performance issues or timeouts
- etc.
"""

MAX_N_PATTERN_CATEGORIES = 7

# =============================================================================
# First Pass Categorization Prompts
# =============================================================================

FIRST_PASS_SYSTEM_PROMPT = f"""
# Task - Trace Pattern Categorization

Your task is to output a draft set of notes and candidate pattern categories given trace data from a user's AI system. \
We are trying to help a user understand key failure modes and behavioral patterns in their AI system.

## Trace Definition

{TRACE_PATTERN_DEFINITION}

### How Your Notes and Candidate Pattern Categories Will Be Used

With this rough draft of pattern categories and notes for 1 or a small number of traces, a later step in this pipeline \
will subsequently compare the draft notes and candidate pattern categories across a larger number of traces. \
From here, we will iteratively align and refine the notes and candidate pattern categories until we \
have a set of pattern categories that are consistent across a larger number of traces.

## Inspiration - Open Coding

This task is similar to open coding, where we are trying to identify the underlying issue and phenomenon:

> Open coding attempts to codify, name or classifying the observed phenomenon and is achieved by segmenting \
data into meaningful expressions and describing that data with a single word or short sequence of words

Some examples of open coding questions to consider when drafting the notes and candidate pattern categories:

- Identify the underlying issue and phenomenon *(What?*)
- Identify the phenomenon's attributes *(What kind?*)
- Determine the time, course and location of the behavior *(When? How long? Where?)*
- Identify the intensity of the issue (*How much? How long?*)
- Identify the reasons attached to the issue (*Why?*)
- Identify intention or purpose of the behavior (*Why?)*

Take inspiration from the above open coding questions but there is no need to be exhaustive if it's not relevant \
to the trace data in question.

## Notes on User-provided Data

### Human Annotations

If human annotations are provided, these represent real observations from human reviewers. Pay close attention to \
annotated error categories or issues, as these are valuable signals for identifying patterns.

### Automated Scores

If automated scores are provided (e.g., from scorers or evaluators), use these as indicators but don't treat them \
as absolute truth. Scores can have false positives or false negatives. Look at the actual trace data to understand \
what's really happening.

### LLM-generated Reasoning

Be cautious if the trace data includes 'thinking', 'reasoning' or 'notes' sections that may have come from an LLM. \
These should not be treated as absolute truth. You can still use clearly correct insights, just be cautious about \
trusting them 100%.
"""

FIRST_PASS_PROMPT = """
Given the specific task context from the user as well as the trace data, please make your best \
guess at the notes and candidate pattern categories for the given trace.

## User context about their AI system

Below is the context from the user about their AI system and what they are trying to analyze. This will help \
you better understand what the user is trying to achieve with their AI system.

<user_context>
{user_context}
</user_context>

{existing_clusters_section}

## Trace Data

### Inputs that were given to the system
<trace_input>
{trace_input}
</trace_input>

### Outputs from the system
<trace_output>
{trace_output}
</trace_output>

### Additional Metadata (scores, timestamps, etc.)

<trace_metadata>
{trace_metadata}
</trace_metadata>
{execution_trace_section}
## Analyze and Draft Notes and Candidate Pattern Categories

With the above user context and trace data, please output a draft set of notes and candidate \
pattern categories for the given trace.

### Specificity of Candidate Pattern Categories

Try and be as specific as possible in your categorizations without literally incorporating every single detail of the \
single trace given. The goal is to identify patterns that will likely appear across multiple traces.

### Style of Candidate Pattern Categories

Ensure that the candidate pattern categories are:
- concise and to the point
- lowercase
- separated by underscores
- no more than 5 words maximum
"""

# =============================================================================
# Clustering Prompts
# =============================================================================

CLUSTERING_SYSTEM_PROMPT = f"""# Task - Clustering Draft Categorizations

Given {{num_traces}} of draft categorizations and notes for a set of traces, cluster \
the categorizations and notes into a defined set of pattern categories.

## Definition - Trace Patterns

{TRACE_PATTERN_DEFINITION}

## Task Context - Clustering Draft Categorizations

The purpose of this task is to examine draft categorizations and notes for a set of traces and cluster the \
categories into a canonical set of pattern categories. The aim is to find a set of pattern categories that \
are consistent across a large number of traces, ideally we have no more than \
{MAX_N_PATTERN_CATEGORIES} pattern categories.

These categories should be specific enough to:
1. Clearly identify failure modes or problematic behaviors
2. Highlight distinct behavioral patterns that could be monitored
3. Be potentially converted into automated scorers for ongoing monitoring

If a trace doesn't fit into any of the defined pattern categories, it should be classified as "other".

Keep all category names lowercase, concise and separated by '_'.
"""

CLUSTERING_PROMPT = f"""
## Draft Categorizations and Notes

Here are the draft categorizations and notes for {{num_traces}} traces:

<draft_categorizations_and_notes>

{{draft_categorizations_and_notes}}
</draft_categorizations_and_notes>

## Output

Output a list of maximum {MAX_N_PATTERN_CATEGORIES} pattern categories - you can output less than \
{MAX_N_PATTERN_CATEGORIES} if you think that's appropriate.
"""

# =============================================================================
# Final Classification Prompts
# =============================================================================

FINAL_CLASSIFICATION_SYSTEM_PROMPT = """
# Task - Final Classification of Traces

You are a helpful assistant that classifies traces into predefined pattern categories.

Your task is to analyze a single trace and classify it into zero or more of the provided pattern categories.

## Important Notes:
- A trace can belong to MULTIPLE categories if it exhibits multiple patterns
- If the trace has NO ERRORS or issues, the pattern_categories list should be EMPTY
- Only assign categories that are clearly supported by the trace data
- Base your classification on the actual trace data, not on assumptions
- Consider the user context to better understand the nature of the behavior or issue
"""

FINAL_CLASSIFICATION_PROMPT = """
Given the following trace data and the list of available pattern categories, \
classify this specific trace into zero or more appropriate categories.

## User Context

<user_context>
{user_context}
</user_context>

{human_annotations_section}

## Trace Data

### Inputs that were given to the system
<trace_input>
{trace_input}
</trace_input>

### Outputs from the system
<trace_output>
{trace_output}
</trace_output>

### Additional Metadata (scores, timestamps, etc.)
<trace_metadata>
{trace_metadata}
</trace_metadata>
{execution_trace_section}
## Available Pattern Categories

<available_pattern_categories>
{available_pattern_categories}
</available_pattern_categories>

## Task

Analyze the above trace and classify it into ZERO or MORE of the available categories.

Important:
- A trace can belong to multiple categories if it exhibits multiple patterns
- If the trace has NO ERRORS or issues, return an empty list for pattern_categories
- Only assign categories that are clearly supported by the evidence in the trace data
"""

# =============================================================================
# Deep Trace Analysis Prompts
# =============================================================================

# Execution trace section - conditionally included when deep_trace_analysis=True
EXECUTION_TRACE_SECTION = """
### Agent Execution Trace

The trace below shows the internal execution flow including tool calls, LLM operations, and timings.

Look for these failure patterns:
- **Tool Use**: Wrong tool, bad parameters, ignored outputs, redundant calls
- **Planning**: Loops, poor ordering, abandoned plans

<agent_execution_trace>
{execution_trace}
</agent_execution_trace>
"""

# Trace compaction prompts
TRACE_COMPACTION_SYSTEM_PROMPT = """You are compacting an agent execution trace for failure analysis.

Your task is to summarize this execution trace concisely while preserving critical information.

PRESERVE (keep exactly as-is or with minimal reduction):
- All tool call names and their key input parameters
- Errors, exceptions, or failure indicators
- Key decision points and reasoning from LLM calls
- Final outputs and results
- The hierarchical structure of the trace

SUMMARIZE/TRUNCATE:
- Verbose intermediate LLM outputs (keep just key decisions)
- Large data payloads in outputs (summarize what type of data)
- Redundant or repetitive information
- Long lists or arrays (indicate count and type)

Output a condensed version of the trace that maintains the tree structure but is more compact."""

TRACE_COMPACTION_USER_PROMPT = """Compact this agent execution trace to approximately {target_tokens} tokens:

{trace_tree}

Output the compacted trace maintaining the tree structure."""

# =============================================================================
# Trace Summary Prompt (for summarize command)
# =============================================================================

TRACE_SUMMARY_SYSTEM_PROMPT = """You are a trace analysis assistant. Your task is to provide a concise, 
actionable summary of an AI system execution trace.

Focus on:
1. **Purpose**: What was the trace trying to accomplish?
2. **Outcome**: Did it succeed or fail? What was the result?
3. **Performance**: Key metrics (latency, token usage, costs if available)
4. **Issues**: Any errors, warnings, or concerning patterns
5. **Recommendations**: Actionable insights for improvement

Be concise but thorough. Use bullet points for clarity."""

TRACE_SUMMARY_USER_PROMPT = """Analyze this trace and provide a summary:

## Trace Metadata
- **Trace ID**: {trace_id}
- **Operation**: {op_name}
- **Duration**: {duration}
- **Status**: {status}
{token_info}
{cost_info}
{feedback_info}

## Execution Tree
{execution_trace}

## Provide Summary

Summarize this trace focusing on:
1. What it was doing
2. Whether it succeeded
3. Any issues or inefficiencies
4. Actionable recommendations
"""

# =============================================================================
# Human Annotations Section Builder
# =============================================================================

def build_human_annotations_section(annotation_summary: dict) -> str:
    """Build the human annotations section for prompts.

    Args:
        annotation_summary: Dict with 'has_annotations' and 'examples' keys

    Returns:
        Formatted string for the annotations section, or empty string if no annotations
    """
    if not annotation_summary.get("has_annotations"):
        return ""

    examples = annotation_summary.get("examples", [])
    if not examples:
        return ""

    section = """
## Human Annotations

The following human annotations were found in the traces. These represent real observations 
from human reviewers and should be given significant weight in your analysis.

"""
    for i, example in enumerate(examples[:3]):
        annotations = example.get("annotations", {})
        section += f"### Example {i + 1}\n"
        for key, value in annotations.items():
            section += f"- **{key}**: {str(value)[:500]}\n"
        section += "\n"

    return section


def build_execution_trace_section(execution_trace: str | None) -> str:
    """Build the execution trace section for prompts.

    Args:
        execution_trace: The formatted execution trace string, or None

    Returns:
        Formatted string for the execution trace section, or empty string if no trace
    """
    if not execution_trace:
        return ""

    return EXECUTION_TRACE_SECTION.format(execution_trace=execution_trace)


def build_existing_clusters_section(existing_clusters: dict | None) -> str:
    """Build the existing clusters section for prompts.

    Args:
        existing_clusters: Dictionary containing existing cluster definitions, or None

    Returns:
        Formatted string for the existing clusters section, or empty string if no clusters
    """
    if not existing_clusters or "clusters" not in existing_clusters:
        return ""

    clusters_list = existing_clusters["clusters"]
    if not clusters_list:
        return ""

    section = """
## Existing Cluster Definitions

The following cluster definitions already exist. When categorizing traces, prefer using these \
existing categories if the trace clearly matches one of them. You can still create new categories \
if the trace exhibits a distinct pattern not covered by the existing ones.

"""
    for i, cluster in enumerate(clusters_list):
        cluster_name = cluster.get("cluster_name", "unknown")
        cluster_def = cluster.get("cluster_definition", "")
        section += f"### Existing Category {i + 1}: {cluster_name}\n"
        section += f"{cluster_def}\n\n"

    return section
