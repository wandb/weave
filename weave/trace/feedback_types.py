"""Feedback type names, and the call fields that select runnable feedback."""

REACTION_FEEDBACK_TYPE = "wandb.reaction.1"
NOTE_FEEDBACK_TYPE = "wandb.note.1"
# Human-applied tags on agents (vs scorer-applied wandb.agent_monitor tags),
# stored in scorer_tags. Covers any human tag, e.g. an emoji reaction or a
# manual label like "low-quality".
AGENT_USER_FEEDBACK_TYPE = "wandb.agent_user_feedback"

RUNNABLE_FEEDBACK_TYPE_PREFIX = "wandb.runnable"


def runnable_feedback_selector(name: str) -> str:
    return f"feedback.[{RUNNABLE_FEEDBACK_TYPE_PREFIX}.{name}]"


def runnable_feedback_output_selector(name: str) -> str:
    return f"{runnable_feedback_selector(name)}.payload.output"


def runnable_feedback_runnable_ref_selector(name: str) -> str:
    return f"{runnable_feedback_selector(name)}.runnable_ref"
