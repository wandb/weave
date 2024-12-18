from typing import Optional

from pydantic import BaseModel

from weave.trace_server.interface.builtin_object_classes import base_object_def


class LeaderboardColumn(BaseModel):
    evaluation_object_ref: base_object_def.RefStr
    scorer_name: str
    summary_metric_path: str
    should_minimize: Optional[bool] = None


class Leaderboard(base_object_def.BaseObject):
    columns: list[LeaderboardColumn]
