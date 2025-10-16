from pydantic import BaseModel


class ServerInfoRes(BaseModel):
    min_required_weave_python_version: str
