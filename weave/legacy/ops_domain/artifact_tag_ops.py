from weave.api import op
from weave.legacy.ops_domain.wb_domain_types import ArtifactTagTypeDict


# Section 1/6: Tag Getters
# None

# Section 2/6: Root Ops
# None

# Section 3/6: Attribute Getters
@op(
    name="artifactTag-name",
)
def op_artifact_tag_name(tag: ArtifactTagTypeDict) -> str:
    return tag["name"]

# Section 4/6: Direct Relationship Ops
# None

# Section 5/6: Connection Ops
# None

# Section 6/6: Non Standard Business Logic Ops
# None
