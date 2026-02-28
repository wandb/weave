"""Pydantic models for trace analysis - based on FAILS models."""

from pydantic import BaseModel, Field


# =============================================================================
# First Pass Categorization Models
# =============================================================================


class FirstPassCategory(BaseModel):
    """A first pass categorization of a single trace."""

    category_name: str = Field(description="The name of the category.")
    category_description: str = Field(
        description="A high-level, generic, short description and justification for the category."
    )
    trace_note: str = Field(
        description="A sentence or two of notes specific to what was observed in this individual trace."
    )


class FirstPassCategorization(BaseModel):
    """First pass classification of a single trace."""

    thinking: str = Field(
        description="A detailed thinking process of the classification."
    )
    first_pass_categories: list[FirstPassCategory] = Field(
        description="A short list of 1-3 first pass categories for the trace."
    )


class FirstPassCategorizationResult(FirstPassCategorization):
    """First pass classification result with trace ID."""

    trace_id: str = Field(description="The ID of the trace that was classified.")


# =============================================================================
# Clustering Models
# =============================================================================


class Category(BaseModel):
    """A pattern category."""

    thinking: str = Field(
        description="A detailed reasoning process behind the selection of the category name, description and notes."
    )
    pattern_category_name: str = Field(
        description="The name of the pattern category. Keep all category names lowercase, concise and separated by '_'. "
        "If a trace doesn't fit into any of the defined pattern categories, it should be classified as 'other'."
    )
    pattern_category_definition: str = Field(
        description="A short definition of the pattern category."
    )
    pattern_category_notes: str = Field(
        description="A sentence or two of notes for the pattern category."
    )


class ClusteringCategories(BaseModel):
    """Clustering of draft categorizations and notes into a set of pattern categories."""

    category_long_list_thinking: str = Field(
        description="A detailed reasoning process and final decision making for the selection of the pattern categories."
    )
    pattern_categories: list[Category] = Field(
        description="A list of pattern categories. "
        "If a trace doesn't fit into any of the defined pattern categories, it should be classified as 'other'."
    )


# =============================================================================
# Final Classification Models
# =============================================================================


class FinalClassification(BaseModel):
    """Final classification of a single trace into predefined categories."""

    thinking: str = Field(
        description="A detailed reasoning process explaining why this specific trace "
        "belongs to the selected categories. Consider the trace characteristics, the category "
        "definitions, and why these are the best matches among all available categories. "
        "Traces can belong to multiple categories if they exhibit multiple patterns. "
        "If the trace has no errors or issues, the pattern_categories list should be empty."
    )
    pattern_categories: list[str] = Field(
        description="List of selected category names from the available pattern categories. "
        "Each category should be one of the provided category names. "
        "A trace can belong to multiple categories if it exhibits multiple patterns. "
        "If the trace has no errors or issues, this should be an empty list."
    )
    categorization_reason: str = Field(
        description="Brief notes explaining any specific aspects of this trace "
        "that influenced the classification decision."
    )


class FinalClassificationResult(FinalClassification):
    """Final classification result with trace ID."""

    trace_id: str = Field(description="The ID of the trace that was classified.")


# =============================================================================
# Pipeline Result Models
# =============================================================================


class PipelineResult(BaseModel):
    """Full pipeline result."""

    pattern_categories: list[Category]
    classifications: list[FinalClassificationResult]
    report: str = ""


# =============================================================================
# Output Models (for CLI)
# =============================================================================


class ClusterResult(BaseModel):
    """A single clustered trace result."""

    trace_id: str
    pattern_category: str
    categorization_reason: str
    trace_url: str


class ClusterGroup(BaseModel):
    """A group of traces in a category."""

    category_name: str
    category_definition: str
    count: int
    percentage: float
    traces: list[ClusterResult]


class ClusterOutput(BaseModel):
    """Output format for cluster command."""

    total_traces: int
    entity: str
    project: str
    clusters: list[ClusterGroup]


# =============================================================================
# Deep Trace Analysis Models
# =============================================================================


class TraceSummary(BaseModel):
    """Summary of a single trace from LLM analysis."""

    trace_id: str
    op_name: str
    duration_ms: float | None = None
    status: str
    purpose: str = Field(description="What the trace was trying to accomplish")
    outcome: str = Field(description="Whether it succeeded and what the result was")
    issues: list[str] = Field(default_factory=list, description="Any errors or concerning patterns")
    recommendations: list[str] = Field(default_factory=list, description="Actionable insights")
    token_usage: dict | None = None
    cost: dict | None = None
    feedback: dict | None = None


class DeepTraceOutput(BaseModel):
    """Output format for deep-trace command."""

    trace_id: str
    entity: str
    project: str
    trace_url: str
    op_name: str
    duration_ms: float | None
    status: str
    tree: str  # ASCII tree representation
    token_usage: dict | None = None
    cost: dict | None = None
    feedback: dict | None = None


# =============================================================================
# YAML Output Models (for cluster command)
# =============================================================================


class YAMLCluster(BaseModel):
    """A single cluster in YAML format."""

    cluster_name: str
    cluster_definition: str
    sample_traces: list[str] = Field(default_factory=list)


class YAMLClustersOutput(BaseModel):
    """Output format for cluster command in YAML."""

    name: str
    description: str | None = None
    weave_project: str
    weave_entity: str
    last_clustering: str
    trace_list: str
    clusters: list[YAMLCluster]
