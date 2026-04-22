import base64
import uuid


def make_project_id(prefix: str) -> str:
    """Generate a unique base64-encoded project id for a test."""
    raw = f"test/{prefix}_{uuid.uuid4().hex[:8]}"
    return base64.b64encode(raw.encode()).decode()
