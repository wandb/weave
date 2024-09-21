from weave_query.weave_query import context_state as _context_state

_loading_builtins_token = _context_state.set_loading_built_ins()

# Exporting these
from . import (
    artifact_alias_ops as artifact_alias_ops,
)
from . import (
    artifact_collection_ops as artifact_collection_ops,
)
from . import (
    artifact_membership_ops as artifact_membership_ops,
)
from . import (
    artifact_type_ops as artifact_type_ops,
)
from . import (
    artifact_version_ops as artifact_version_ops,
)
from . import (
    entity_ops,
    org_ops,
    project_ops,
    user_ops,
)
from . import (
    repo_insight_ops as repo_insight_ops,
)
from . import (
    report_ops as report_ops,
)
from . import (
    run_ops as run_ops,
)
from . import (
    run_queue_ops as run_queue_ops,
)
from . import (
    stream_table_ops as stream_table_ops,
)
from . import (
    wbgqlquery_op as wbgqlquery_op,
)
from .table import *
from .trace_tree import *

# TODO: Investigate these
from .wbmedia import *

# from . import wbartifact
# from . import file_wbartifact
# from .. import artifacts_local


# make root ops top level
viewer = user_ops.root_viewer  # type: ignore
project = project_ops.project  # type: ignore
entity = entity_ops.entity  # type: ignore
org = org_ops.org  # type: ignore

_context_state.clear_loading_built_ins(_loading_builtins_token)
